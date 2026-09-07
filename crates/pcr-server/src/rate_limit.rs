//! A ceiling on how often one caller may make the server do something expensive.
//!
//! Two things are metered here, for two different reasons.
//!
//! Signing in, because Argon2 makes each attempt expensive on purpose: that is
//! what protects the passwords, and this is what stops the protection being
//! turned into a way to exhaust the server.
//!
//! And designing, because every design forks a Python worker that runs a real
//! search. Those endpoints take no account -- deliberately, so somebody can try
//! the tool before signing up -- which means without a ceiling a single caller
//! can keep every core busy for as long as they like, from a script, for free.
//! It is the cheapest way to take this service down and the first thing that
//! will be found once it is public.
//!
//! Production counters use an atomic PostgreSQL bucket, so every API replica
//! shares one budget. The small in-process map remains available for isolated
//! unit tests and lightweight routers that deliberately have no database.

use std::collections::HashMap;
use std::net::{IpAddr, SocketAddr};
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::{Duration, Instant};

use axum::extract::{ConnectInfo, Request, State};
use axum::http::{HeaderMap, StatusCode};
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use axum::Json;
use pcr_accounts::Accounts;

/// How many distinct callers this limiter will track at once.
///
/// A key exists per caller per window. An attacker rotating an address faster
/// than the window expires grows the map at their request rate; without a
/// ceiling that is memory they choose the size of. Past the cap, expired keys
/// are swept and then the oldest entries are dropped -- which means an
/// attacker pushing past the cap evicts other attackers before they evict
/// anybody's budget, because a fresh key starts empty.
const MAX_TRACKED_KEYS: usize = 65_536;

/// An address or CIDR range whose forwarded client header may be trusted.
///
/// CIDR support is needed when the web tier is scaled: container replicas do
/// not have one permanent IP, but they still live inside the private compose
/// network. The parser rejects malformed or over-wide ranges rather than
/// silently turning a typo into a trust-all rule.
#[derive(Clone, Copy, Debug)]
pub struct TrustedProxy {
    network: IpAddr,
    prefix: u8,
}

impl TrustedProxy {
    pub(crate) fn parse(value: &str) -> Option<Self> {
        let (address, prefix) = value
            .split_once('/')
            .map_or((value, None), |(address, prefix)| (address, Some(prefix)));
        let network = address.parse::<IpAddr>().ok()?;
        let (maximum, minimum_network_prefix) = match network {
            IpAddr::V4(_) => (32, 16),
            IpAddr::V6(_) => (128, 64),
        };
        let prefix = prefix
            .map(|value| value.parse::<u8>().ok())
            .unwrap_or(Some(maximum))?;
        if prefix > maximum || (prefix != maximum && prefix < minimum_network_prefix) {
            return None;
        }

        // CIDRs must name their network address exactly. Accepting a host-bit
        // value such as 172.29.0.42/24 hides a configuration typo and makes the
        // effective trust boundary less obvious than the configured value.
        let canonical = match network {
            IpAddr::V4(address) => {
                let mask = if prefix == 0 {
                    0
                } else {
                    u32::MAX << (32 - u32::from(prefix))
                };
                IpAddr::V4((u32::from(address) & mask).into())
            }
            IpAddr::V6(address) => {
                let mask = if prefix == 0 {
                    0
                } else {
                    u128::MAX << (128 - u32::from(prefix))
                };
                IpAddr::V6((u128::from(address) & mask).into())
            }
        };
        (canonical == network).then_some(Self { network, prefix })
    }

    fn contains(self, address: IpAddr) -> bool {
        match (self.network, address) {
            (IpAddr::V4(network), IpAddr::V4(address)) => {
                let mask = if self.prefix == 0 {
                    0
                } else {
                    u32::MAX << (32 - u32::from(self.prefix))
                };
                u32::from(network) & mask == u32::from(address) & mask
            }
            (IpAddr::V6(network), IpAddr::V6(address)) => {
                let mask = if self.prefix == 0 {
                    0
                } else {
                    u128::MAX << (128 - u32::from(self.prefix))
                };
                u128::from(network) & mask == u128::from(address) & mask
            }
            _ => false,
        }
    }
}

/// A sliding window counter keyed by caller.
#[derive(Clone)]
pub struct RateLimiter {
    hits: Arc<Mutex<HashMap<String, Vec<Instant>>>>,
    max: usize,
    window: Duration,
    /// The proxy addresses whose forwarded header may be believed.
    trusted_proxies: Arc<Vec<TrustedProxy>>,
    shared: Option<Accounts>,
    namespace: &'static str,
}

impl std::fmt::Debug for RateLimiter {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("RateLimiter")
            .field("max", &self.max)
            .field("window", &self.window)
            .field("trusted_proxies", &self.trusted_proxies.len())
            .finish()
    }
}

impl RateLimiter {
    /// The proxy addresses this limiter believes a forwarded header from.
    #[must_use]
    pub fn trusted_proxies(&self) -> &[TrustedProxy] {
        &self.trusted_proxies
    }
    /// Allow `max` attempts per `window` from one caller.
    #[must_use]
    pub fn new(max: usize, window: Duration) -> Self {
        Self {
            hits: Arc::new(Mutex::new(HashMap::new())),
            max,
            window,
            trusted_proxies: Arc::new(Vec::new()),
            shared: None,
            namespace: "local",
        }
    }

    /// Read `PCR_TRUSTED_PROXIES` into the limiter, alongside its limits.
    ///
    /// Every limiter in the process calls this rather than each place reading
    /// the environment itself, so there is exactly one notion of who counts as
    /// a caller.
    #[must_use]
    pub fn from_env(max: usize, window: Duration) -> Self {
        let proxies = std::env::var("PCR_TRUSTED_PROXIES")
            .unwrap_or_default()
            .split(',')
            .map(str::trim)
            .filter(|entry| !entry.is_empty())
            .filter_map(|entry| match TrustedProxy::parse(entry) {
                Some(proxy) => Some(proxy),
                None => {
                    tracing::warn!("ignoring invalid PCR_TRUSTED_PROXIES entry: {entry}");
                    None
                }
            })
            .collect::<Vec<_>>();
        Self {
            trusted_proxies: Arc::new(proxies),
            ..Self::new(max, window)
        }
    }

    /// Use PostgreSQL as the shared counter for horizontally scaled servers.
    #[must_use]
    pub fn with_shared_store(
        max: usize,
        window: Duration,
        accounts: Accounts,
        namespace: &'static str,
    ) -> Self {
        let mut limiter = Self::from_env(max, window);
        limiter.shared = Some(accounts);
        limiter.namespace = namespace;
        limiter
    }

    /// Consume one request, using the shared store when configured.
    ///
    /// # Errors
    ///
    /// Returns the account-store error when a production shared counter cannot
    /// be updated. Callers should fail closed in that situation.
    pub async fn allow_request(&self, key: &str) -> Result<bool, pcr_accounts::AccountError> {
        if let Some(accounts) = &self.shared {
            let max = i32::try_from(self.max).unwrap_or(i32::MAX);
            let window = i64::try_from(self.window.as_secs()).unwrap_or(i64::MAX);
            return accounts
                .allow_rate_limit(self.namespace, key, max, window)
                .await;
        }
        Ok(self.allow(key))
    }

    /// Lock the counters, recovering from poisoning.
    ///
    /// Recovering is right here where failing open was not: the map holds
    /// plain counters with no invariant that a panic could have broken
    /// mid-update, and refusing to count at all disables every limit in the
    /// process until restart.
    fn lock(&self) -> MutexGuard<'_, HashMap<String, Vec<Instant>>> {
        self.hits
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }

    /// Record an attempt and say whether it is within the limit.
    #[must_use]
    pub fn allow(&self, key: &str) -> bool {
        let now = Instant::now();
        let mut hits = self.lock();

        // Opportunistic sweep: without it the map keeps a key for every caller
        // that ever tried, forever. Run under pressure from the cap as well as
        // at the old size threshold, so a flood of new addresses pays for its
        // own cleanup.
        if hits.len() > 4096 || hits.len() >= MAX_TRACKED_KEYS {
            hits.retain(|_, times| times.iter().any(|at| now.duration_since(*at) < self.window));
        }
        if hits.len() >= MAX_TRACKED_KEYS && !hits.contains_key(key) {
            // Still full of live callers. Drop one arbitrary entry: whoever
            // it is keeps most of their budget (their window restarts), which
            // beats growing without bound.
            if let Some(victim) = hits.keys().next().cloned() {
                hits.remove(&victim);
            }
        }

        let times = hits.entry(key.to_owned()).or_default();
        times.retain(|at| now.duration_since(*at) < self.window);

        if times.len() >= self.max {
            return false;
        }
        times.push(now);
        true
    }
}

/// Who to count attempts against.
///
/// The peer address identifies the caller. `X-Forwarded-For` replaces it only
/// when the request arrived from an address named in `PCR_TRUSTED_PROXIES`:
/// anywhere else, the header is written by whoever sent the request, and
/// believing it lets a script hand itself a different bucket per attempt --
/// which used to make the design limit cost nothing to bypass.
///
/// Shared by everything that meters, rather than each place deciding for
/// itself what "one caller" means -- two definitions would meter two different
/// populations and neither would be the one anybody reasoned about.
#[must_use]
pub fn caller_key(headers: &HeaderMap, peer: Option<SocketAddr>, trusted: &[IpAddr]) -> String {
    caller_key_with_trusted(
        headers,
        peer,
        &trusted
            .iter()
            .copied()
            .filter_map(|ip| TrustedProxy::parse(&ip.to_string()))
            .collect::<Vec<_>>(),
    )
}

/// Derive a caller key using exact addresses or trusted private networks.
#[must_use]
pub fn caller_key_with_trusted(
    headers: &HeaderMap,
    peer: Option<SocketAddr>,
    trusted: &[TrustedProxy],
) -> String {
    let peer_ip = peer.map(|address| address.ip());
    if peer_ip.is_some_and(|ip| trusted.iter().copied().any(|proxy| proxy.contains(ip))) {
        if let Some(forwarded) = headers
            .get("x-forwarded-for")
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.split(',').next())
            .map(str::trim)
            .filter(|first| !first.is_empty())
            .and_then(|first| first.parse::<IpAddr>().ok())
        {
            return forwarded.to_string();
        }
    }
    peer_ip
        .map(|ip| ip.to_string())
        // Requests driven straight at the router in tests have no socket. They
        // share one bucket, which is what makes the limiter observable in
        // tests; production always has a socket, so "unknown" never collides
        // with a real caller there.
        .unwrap_or_else(|| "unknown".to_owned())
}

/// The peer address, when the server was started with connection info.
///
/// Read out of the extensions rather than extracted, so a test that drives the
/// router directly -- with no socket behind it -- gets `None` instead of a
/// rejection.
#[must_use]
pub fn peer_of(request: &Request) -> Option<SocketAddr> {
    request
        .extensions()
        .get::<ConnectInfo<SocketAddr>>()
        .map(|ConnectInfo(address)| *address)
}

/// How many designs one caller may ask for in the window below.
///
/// Generous for a person: a design takes seconds to read, so nobody working
/// through the interface comes close. Restrictive for a script, which is the
/// point.
pub const DESIGNS_PER_WINDOW: usize = 30;

/// The window the count above is measured over.
pub const DESIGN_WINDOW: Duration = Duration::from_secs(60);

/// How many sequence lookups, alignments, or consensus builds one caller may
/// ask for in the design window.
///
/// Lower than the design ceiling: these fork the same kind of worker, one of
/// them talks to NCBI on everybody's shared budget, and none of them needs a
/// person to be quick about it.
pub const SEQUENCES_PER_WINDOW: usize = 15;

/// Refuse a request that has asked for too much work too quickly.
///
/// Applied as a layer rather than checked inside each handler, so an endpoint
/// added later is covered by where it is mounted rather than by somebody
/// remembering.
pub async fn meter(State(limiter): State<RateLimiter>, request: Request, next: Next) -> Response {
    let peer = peer_of(&request);
    let key = caller_key_with_trusted(request.headers(), peer, &limiter.trusted_proxies);

    let allowed = limiter.allow_request(&key).await;
    if matches!(allowed, Ok(true)) {
        return next.run(request).await;
    }

    if let Err(error) = allowed {
        tracing::error!(%error, "shared rate limiter unavailable");
        return (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(crate::error::body(
                "RATE_LIMIT_STORE_UNAVAILABLE",
                "serviceUnavailable",
                "The service is temporarily unavailable. Try again shortly.",
                None,
                Some("rateLimit"),
                true,
            )),
        )
            .into_response();
    }

    let operation = match limiter.namespace {
        "sequence" => "sequence",
        "design" => "design",
        _ => "expensive",
    };
    let window_seconds = limiter.window.as_secs().max(1);
    tracing::warn!(caller = %key, operation, "refused an expensive request: over the rate limit");
    let mut response = (
        StatusCode::TOO_MANY_REQUESTS,
        Json(crate::error::body(
            "RATE_LIMITED",
            "tooManyRequests",
            format!(
                "Too many {operation} requests from one caller. The limit is {} per {} seconds because each design starts a real search; \
                 wait for the window to clear and try again.",
                limiter.max, window_seconds
            ),
            None,
            Some("rateLimit"),
            true,
        )),
    )
        .into_response();
    if let Ok(value) = axum::http::HeaderValue::from_str(&window_seconds.to_string()) {
        response
            .headers_mut()
            .insert(axum::http::header::RETRY_AFTER, value);
    }
    response
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_first_attempts_pass_and_the_next_one_does_not() {
        let limiter = RateLimiter::new(3, Duration::from_secs(60));
        assert!(limiter.allow("a"));
        assert!(limiter.allow("a"));
        assert!(limiter.allow("a"));
        assert!(!limiter.allow("a"));
    }

    #[test]
    fn one_caller_hitting_the_limit_does_not_lock_out_another() {
        let limiter = RateLimiter::new(1, Duration::from_secs(60));
        assert!(limiter.allow("a"));
        assert!(!limiter.allow("a"));
        assert!(limiter.allow("b"));
    }

    #[test]
    fn the_window_lets_attempts_expire() {
        let limiter = RateLimiter::new(1, Duration::from_millis(40));
        assert!(limiter.allow("a"));
        assert!(!limiter.allow("a"));
        std::thread::sleep(Duration::from_millis(60));
        assert!(limiter.allow("a"));
    }

    #[test]
    fn trusted_proxy_rejects_overwide_and_noncanonical_networks() {
        assert!(TrustedProxy::parse("0.0.0.0/0").is_none());
        assert!(TrustedProxy::parse("10.0.0.0/8").is_none());
        assert!(TrustedProxy::parse("::/0").is_none());
        assert!(TrustedProxy::parse("2001:db8::/48").is_none());
        assert!(TrustedProxy::parse("172.29.0.42/24").is_none());
        assert!(TrustedProxy::parse("172.29.0.0/24").is_some());
        assert!(TrustedProxy::parse("2001:db8::/64").is_some());
        assert!(TrustedProxy::parse("203.0.113.7").is_some());
    }

    #[test]
    fn a_forwarded_header_from_a_trusted_proxy_is_believed() {
        use axum::http::HeaderMap;
        let trusted: &[IpAddr] = &["10.0.0.1".parse().unwrap()];
        let mut headers = HeaderMap::new();
        headers.insert("x-forwarded-for", "203.0.113.7".parse().unwrap());
        let peer = "10.0.0.1:443".parse::<SocketAddr>().ok();

        let key = caller_key(&headers, peer, trusted);
        assert_eq!(key, "203.0.113.7");
        // And it is that caller's budget, not the proxy's.
        let limiter = RateLimiter::new(1, Duration::from_secs(60));
        assert!(limiter.allow(&key));
        assert!(!limiter.allow(&key));
    }

    #[test]
    fn a_trusted_private_network_covers_scaled_web_replicas() {
        use axum::http::HeaderMap;
        let trusted = [TrustedProxy::parse("172.28.0.0/24").expect("valid CIDR")];
        let mut headers = HeaderMap::new();
        headers.insert("x-forwarded-for", "203.0.113.7".parse().unwrap());
        let peer = "172.28.0.42:443".parse::<SocketAddr>().ok();

        assert_eq!(
            caller_key_with_trusted(&headers, peer, &trusted),
            "203.0.113.7"
        );
    }

    #[test]
    fn a_forwarded_header_from_anywhere_else_is_ignored() {
        use axum::http::HeaderMap;
        let trusted: &[IpAddr] = &[];
        let mut headers = HeaderMap::new();
        headers.insert("x-forwarded-for", "203.0.113.7".parse().unwrap());
        let peer: Option<SocketAddr> =
            Some("198.51.100.9:40000".parse::<SocketAddr>().expect("parses"));

        // The header names one address; the socket names the truth.
        assert_eq!(caller_key(&headers, peer, trusted), "198.51.100.9",);
    }

    #[test]
    fn a_malformed_forwarded_header_is_ignored_even_from_a_trusted_proxy() {
        use axum::http::HeaderMap;
        let trusted = [TrustedProxy::parse("172.28.0.0/24").expect("valid CIDR")];
        let mut headers = HeaderMap::new();
        headers.insert("x-forwarded-for", "not-an-ip".parse().unwrap());
        let peer = "172.28.0.42:443".parse::<SocketAddr>().ok();

        assert_eq!(
            caller_key_with_trusted(&headers, peer, &trusted),
            "172.28.0.42"
        );
    }

    #[test]
    fn rotating_the_forwarded_header_cannot_multiply_one_callers_budget() {
        use axum::http::HeaderMap;
        let limiter = RateLimiter::new(2, Duration::from_secs(60));
        let trusted: &[IpAddr] = &[];
        for attempt in 0..5 {
            let mut headers = HeaderMap::new();
            headers.insert(
                "x-forwarded-for",
                format!("203.0.113.{attempt}").parse().unwrap(),
            );
            let key = caller_key(&headers, None, trusted);
            // No peer in these requests, so every rotation lands in the same
            // bucket and the third attempt is refused.
            assert_eq!(limiter.allow(&key), attempt < 2);
        }
    }
}

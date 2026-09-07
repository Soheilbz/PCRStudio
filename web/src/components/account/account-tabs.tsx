"use client";

import { FlaskConical, Shield, Trash2, User, type LucideIcon } from "lucide-react";
import { useRef, useState, type KeyboardEvent } from "react";

import {
  DeleteAccountCard,
  EmailForm,
  ExportCard,
  PasswordForm,
  ProfileForm,
  RecoveryCodeCard,
  SessionsCard,
} from "@/components/account/account-forms";
import { AppearanceSettings } from "@/components/settings/appearance-settings";
import { BenchSettings } from "@/components/settings/bench-settings";
import type { Preferences, RecoveryStatus, User as UserType } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export interface AccountTabsProps {
  user: UserType;
  preferences: Preferences;
  polymerases: { id: string; name: string; summary: string }[];
  recovery: RecoveryStatus | { unavailable: true } | null;
}

type TabId = "bench" | "profile" | "security" | "danger";

interface TabItem {
  id: TabId;
  label: string;
  icon: LucideIcon;
}

const TABS: TabItem[] = [
  {
    id: "bench",
    label: "Bench & Appearance",
    icon: FlaskConical,
  },
  {
    id: "profile",
    label: "Profile & Data",
    icon: User,
  },
  {
    id: "security",
    label: "Security & Sessions",
    icon: Shield,
  },
  {
    id: "danger",
    label: "Danger Zone",
    icon: Trash2,
  },
];

export function AccountTabs({ user, preferences, polymerases, recovery }: AccountTabsProps) {
  const [activeTab, setActiveTab] = useState<TabId>("bench");
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({});

  const focusTab = (tabId: TabId) => {
    setActiveTab(tabId);
    tabRefs.current[tabId]?.focus();
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, tabId: TabId) => {
    const index = TABS.findIndex((tab) => tab.id === tabId);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      focusTab(TABS[(index + 1) % TABS.length]!.id);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      focusTab(TABS[(index - 1 + TABS.length) % TABS.length]!.id);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusTab(TABS[0]!.id);
    } else if (event.key === "End") {
      event.preventDefault();
      focusTab(TABS[TABS.length - 1]!.id);
    }
  };

  return (
    <div className="space-y-6">
      {/* Category Navigation Pills */}
      <nav
        aria-label="Settings sections"
        className="rounded-xl border border-border/70 bg-surface-wash/45 p-1.5 shadow-xs"
      >
        <ul className="flex flex-wrap gap-1 sm:gap-1.5" role="tablist">
          {TABS.map((tab) => {
            const active = activeTab === tab.id;
            const Icon = tab.icon;
            const isDanger = tab.id === "danger";

            return (
              <li key={tab.id}>
                <button
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  ref={(element) => {
                    tabRefs.current[tab.id] = element;
                  }}
                  id={`account-tab-${tab.id}`}
                  role="tab"
                  aria-selected={active}
                  aria-controls={`account-panel-${tab.id}`}
                  tabIndex={active ? 0 : -1}
                  onKeyDown={(event) => handleTabKeyDown(event, tab.id)}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-all focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    active
                      ? isDanger
                        ? "border border-destructive/30 bg-destructive/10 text-destructive shadow-xs"
                        : "border border-primary/20 bg-primary/10 font-semibold text-primary shadow-xs"
                      : "border border-transparent text-muted-foreground hover:bg-surface-warm/45 hover:text-foreground",
                  )}
                >
                  <Icon
                    className={cn(
                      "size-3.5",
                      isDanger && active
                        ? "text-destructive"
                        : active
                          ? "text-primary"
                          : "text-muted-foreground",
                    )}
                  />
                  <span>{tab.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Tab Panels */}
      <div>
        {activeTab === "bench" && (
          <div
            id="account-panel-bench"
            role="tabpanel"
            aria-labelledby="account-tab-bench"
            className="space-y-6"
          >
            <div>
              <h2 className="font-serif text-lg font-semibold text-foreground">
                Laboratory & Display Preferences
              </h2>
              <p className="text-xs text-muted-foreground">
                Configure your default workbench settings and UI appearance.
              </p>
            </div>
            <div className="grid items-start gap-6 md:grid-cols-2">
              <BenchSettings preferences={preferences} polymerases={polymerases} />
              <AppearanceSettings />
            </div>
          </div>
        )}

        {activeTab === "profile" && (
          <div
            id="account-panel-profile"
            role="tabpanel"
            aria-labelledby="account-tab-profile"
            className="space-y-6"
          >
            <div>
              <h2 className="font-serif text-lg font-semibold text-foreground">
                Profile & Project Data Backups
              </h2>
              <p className="text-xs text-muted-foreground">
                Manage your identity and export your projects database.
              </p>
            </div>
            <div className="grid items-start gap-6 md:grid-cols-2">
              <div className="space-y-6">
                <ProfileForm user={user} />
                <EmailForm user={user} />
              </div>
              <ExportCard />
            </div>
          </div>
        )}

        {activeTab === "security" && (
          <div
            id="account-panel-security"
            role="tabpanel"
            aria-labelledby="account-tab-security"
            className="space-y-6"
          >
            <div>
              <h2 className="font-serif text-lg font-semibold text-foreground">
                Security & Active Sessions
              </h2>
              <p className="text-xs text-muted-foreground">
                Manage your login credentials, recovery tokens, and browser sessions.
              </p>
            </div>
            <div className="grid items-start gap-6 md:grid-cols-2">
              <div className="space-y-6">
                <PasswordForm />
                <SessionsCard />
              </div>
              <RecoveryCodeCard status={recovery} />
            </div>
          </div>
        )}

        {activeTab === "danger" && (
          <div
            id="account-panel-danger"
            role="tabpanel"
            aria-labelledby="account-tab-danger"
            className="max-w-2xl space-y-6"
          >
            <div>
              <h2 className="font-serif text-lg font-semibold text-destructive">Danger Zone</h2>
              <p className="text-xs text-muted-foreground">
                Irreversible operations. Please proceed with caution.
              </p>
            </div>
            <DeleteAccountCard user={user} />
          </div>
        )}
      </div>
    </div>
  );
}

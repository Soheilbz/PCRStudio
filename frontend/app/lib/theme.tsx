import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { Moon, Sun } from 'lucide-react';
const ThemeContext = createContext({ theme: 'light', toggle: () => {} });
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    typeof window === 'undefined'
      ? 'light'
      : ((localStorage.getItem('pcrstudio-theme') as 'light' | 'dark' | null) ??
        (matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light')),
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const preference = matchMedia('(prefers-color-scheme: dark)');
    const update = (event: MediaQueryListEvent) => {
      if (!localStorage.getItem('pcrstudio-theme'))
        setTheme(event.matches ? 'dark' : 'light');
    };
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);
  return (
    <ThemeContext.Provider
      value={{
        theme,
        toggle: () => {
          const next = theme === 'light' ? 'dark' : 'light';
          localStorage.setItem('pcrstudio-theme', next);
          setTheme(next);
        },
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}
export function ThemeToggle() {
  const { theme, toggle } = useContext(ThemeContext);
  return (
    <button
      className="icon-button"
      aria-label={`Use ${theme === 'light' ? 'dark' : 'light'} theme`}
      onClick={toggle}
    >
      {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
    </button>
  );
}

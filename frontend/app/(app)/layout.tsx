"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";

import { useRequireAuth } from "@/lib/auth-context";
import { Spinner } from "@/components/spinner";

const NAV = [
  { href: "/", label: "Requests" },
  { href: "/requests/new", label: "New request" },
  { href: "/publishing-queue", label: "Publishing queue" },
  { href: "/admin/access", label: "Access" },
];

export default function AppLayout({ children }: LayoutProps<"/">) {
  const { user, loading, logout } = useRequireAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  if (loading || !user) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="flex animate-fade-in items-center gap-2 text-sm text-muted">
          <Spinner size="medium" />
          Loading…
        </p>
      </main>
    );
  }

  const handleLogout = async () => {
    setMenuOpen(false);
    await logout();
    router.push("/login");
  };

  return (
    <div className="flex flex-1 flex-col bg-surface-base">
      <header className="border-b border-surface-border bg-surface-card/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-8">
            <span className="truncate font-semibold tracking-tight text-foreground">Koya Content Agent</span>
            <nav className="hidden items-center gap-1 md:flex">
              {NAV.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${
                      active ? "bg-primary/10 font-medium text-primary" : "text-muted hover:text-foreground"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="hidden items-center gap-3 text-sm text-muted md:flex">
            <span className="max-w-[220px] truncate">{user.email}</span>
            <button
              onClick={handleLogout}
              className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-foreground transition-colors duration-150 hover:bg-surface-card-hover"
            >
              Log out
            </button>
          </div>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            className="rounded-md border border-surface-border p-2 text-foreground md:hidden"
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {menuOpen && (
          <div className="border-t border-surface-border px-4 py-3 md:hidden">
            <nav className="flex flex-col gap-1">
              {NAV.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className={`rounded-md px-3 py-2 text-sm transition-colors duration-150 ${
                      active ? "bg-primary/10 font-medium text-primary" : "text-muted hover:text-foreground"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
            <div className="mt-3 flex items-center justify-between border-t border-surface-border pt-3 text-sm text-muted">
              <span className="min-w-0 truncate">{user.email}</span>
              <button
                onClick={handleLogout}
                className="shrink-0 rounded-md border border-surface-border px-3 py-1.5 text-sm text-foreground transition-colors duration-150 hover:bg-surface-card-hover"
              >
                Log out
              </button>
            </div>
          </div>
        )}
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</main>
    </div>
  );
}

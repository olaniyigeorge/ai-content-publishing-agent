"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

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

  return (
    <div className="flex flex-1 flex-col bg-surface-base">
      <header className="border-b border-surface-border bg-surface-card/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <span className="font-semibold tracking-tight text-foreground">Koya Content Agent</span>
            <nav className="flex items-center gap-1">
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
          <div className="flex items-center gap-3 text-sm text-muted">
            <span>{user.email}</span>
            <button
              onClick={async () => {
                await logout();
                router.push("/login");
              }}
              className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-foreground transition-colors duration-150 hover:bg-surface-card-hover"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}

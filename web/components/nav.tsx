"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth-provider";

interface NavLink {
  href: string;
  label: string;
}

const patientLinks: NavLink[] = [
  { href: "/patient/dashboard", label: "Dashboard" },
  { href: "/patient/documents", label: "Documents" },
  { href: "/patient/chat", label: "Chat" },
];

const doctorLinks: NavLink[] = [
  { href: "/doctor/dashboard", label: "Dashboard" },
  { href: "/doctor/patients", label: "Patients" },
  { href: "/doctor/appointments", label: "Appointments" },
  { href: "/doctor/scribe", label: "Scribe" },
];

export default function Nav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  const links = user?.role === "doctor" ? doctorLinks : patientLinks;

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <header className="bg-white border-b border-slate-200">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex items-center h-16 gap-8">
          {/* Brand */}
          <Link
            href={user?.role === "doctor" ? "/doctor/dashboard" : "/patient/dashboard"}
            className="flex items-center gap-2 font-bold text-slate-900 text-lg"
          >
            <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg
                className="w-4 h-4 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                />
              </svg>
            </div>
            Decode
          </Link>

          {/* Navigation Links */}
          {user && (
            <nav className="hidden md:flex items-center gap-1 flex-1">
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive(link.href)
                      ? "bg-blue-50 text-blue-700"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          )}

          {/* Right side */}
          {user && (
            <div className="ml-auto flex items-center gap-3">
              {/* User info */}
              <div className="hidden sm:flex flex-col items-end">
                <span className="text-sm font-medium text-slate-900">
                  {user.role === "doctor" ? "Dr. " : ""}
                  {user.firstName} {user.lastName}
                </span>
                <span className="text-xs text-slate-400 capitalize">{user.role}</span>
              </div>

              {/* Avatar */}
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-semibold">
                {user.firstName?.[0] ?? "?"}
              </div>

              {/* Logout */}
              <button
                onClick={logout}
                className="ml-2 text-sm text-slate-500 hover:text-slate-900 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

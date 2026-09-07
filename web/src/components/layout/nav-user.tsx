"use client";

import { ChevronsUpDown, Info, LogIn, LogOut, UserPlus, UserRound } from "lucide-react";
import Link from "next/link";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import type { User } from "@/lib/api/types";
import { signOutAction } from "@/lib/auth/actions";

/** Up to two letters, from however many words the name has. */
function initials(name: string): string {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0])
    .filter(Boolean);
  const first = letters[0] ?? "";
  const last = letters.length > 1 ? (letters[letters.length - 1] ?? "") : "";
  return (first + last).toUpperCase() || "?";
}

/**
 * The account corner of the sidebar.
 *
 * Signed out it says so plainly rather than showing a placeholder person, and
 * offers the two ways to change that.
 */
export function NavUser({ user }: { user: User | null }) {
  const { isMobile } = useSidebar();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="data-[popup-open]:bg-sidebar-accent data-[popup-open]:text-sidebar-accent-foreground"
              />
            }
          >
            <Avatar className="size-8 rounded-lg">
              <AvatarFallback className="rounded-lg bg-sidebar-accent text-xs font-medium text-sidebar-accent-foreground">
                {user ? initials(user.displayName) : <UserRound className="size-4" />}
              </AvatarFallback>
            </Avatar>
            <div className="grid flex-1 text-left leading-tight">
              <span className="truncate text-sm font-medium">
                {user ? user.displayName : "Guest"}
              </span>
              <span className="truncate text-xs text-muted-foreground">
                {user ? user.email : "Not signed in"}
              </span>
            </div>
            <ChevronsUpDown className="ml-auto size-4" />
          </DropdownMenuTrigger>

          <DropdownMenuContent
            className="w-(--anchor-width) min-w-60 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            {/* A header, not a label for the items below it — and Base UI
                throws if a group label sits outside a group. */}
            <div className="px-1.5 py-1">
              <div className="grid gap-0.5 leading-tight">
                <span className="text-sm font-medium">{user ? user.displayName : "Guest"}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {user ? user.email : "Work is not saved between visits."}
                </span>
              </div>
            </div>

            <DropdownMenuSeparator />

            <DropdownMenuGroup>
              <DropdownMenuItem render={<Link href="/account" />}>
                <UserRound />
                Account
              </DropdownMenuItem>
              <DropdownMenuItem render={<Link href="/about" />}>
                <Info />
                About PCRStudio
              </DropdownMenuItem>
            </DropdownMenuGroup>

            <DropdownMenuSeparator />

            {user ? (
              <form action={signOutAction}>
                {/* Menu items are not native buttons by default; this one has
                    to be, because it submits the sign-out form. */}
                <DropdownMenuItem nativeButton render={<button type="submit" className="w-full" />}>
                  <LogOut />
                  Sign out
                </DropdownMenuItem>
              </form>
            ) : (
              <DropdownMenuGroup>
                <DropdownMenuItem render={<Link href="/sign-in" />}>
                  <LogIn />
                  Sign in
                </DropdownMenuItem>
                <DropdownMenuItem render={<Link href="/sign-up" />}>
                  <UserPlus />
                  Create an account
                </DropdownMenuItem>
              </DropdownMenuGroup>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

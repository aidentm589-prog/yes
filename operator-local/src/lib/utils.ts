import { clsx, type ClassValue } from "clsx";
import { formatDistanceToNow, formatISO } from "date-fns";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDateTime(value: string | Date | null | undefined) {
  if (!value) {
    return "Not available";
  }

  return formatISO(typeof value === "string" ? new Date(value) : value);
}

export function formatRelativeTime(value: string | Date | null | undefined) {
  if (!value) {
    return "Just now";
  }

  return formatDistanceToNow(typeof value === "string" ? new Date(value) : value, {
    addSuffix: true,
  });
}

export function truncate(value: string, max = 180) {
  if (value.length <= max) {
    return value;
  }

  return `${value.slice(0, max - 1)}…`;
}

export function safeJsonParse<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function toSlug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Utility to merge Tailwind CSS class names with conflict resolution.
 * Used by shadcn/ui components throughout the dashboard.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

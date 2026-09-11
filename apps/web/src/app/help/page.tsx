import type { Metadata } from "next";
import { HelpHome } from "@/features/help/components/help-home";
import { helpCategories, type HelpCategory } from "@/features/help/types";

export const metadata: Metadata = { title: "Centro de ayuda | Vetflow" };

export default function HelpPage({ searchParams }: { searchParams: { category?: string | string[] } }) {
  const value = searchParams.category;
  const category = typeof value === "string" && Object.hasOwn(helpCategories, value) ? value as HelpCategory : undefined;
  return <HelpHome key={category ?? "all"} initialCategory={category} />;
}

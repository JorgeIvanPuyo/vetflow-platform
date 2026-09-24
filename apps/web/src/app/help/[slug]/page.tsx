import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { HelpArticle } from "@/features/help/components/help-article";
import { helpGuides } from "@/features/help/content";

export function generateStaticParams() {
  return helpGuides.map(({ slug }) => ({ slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const guide = helpGuides.find((item) => item.slug === params.slug);
  return { title: guide ? `${guide.title} | Centro de ayuda` : "Guía no encontrada | Centro de ayuda" };
}

export default function HelpGuidePage({ params }: { params: { slug: string } }) {
  const guide = helpGuides.find((item) => item.slug === params.slug);
  if (!guide) notFound();
  return <HelpArticle guide={guide} />;
}

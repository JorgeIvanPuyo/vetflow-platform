import Link from "next/link";

import { GlobalSearch } from "@/features/search/components/global-search";

export function AppHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="brand" href="/">
          <span className="brand__mark">V</span>
          <span>Vetflow</span>
        </Link>

        <nav className="site-nav" aria-label="Primary">
          <Link href="/">Dashboard</Link>
          <Link href="/owners">Owners</Link>
          <Link href="/patients">Patients</Link>
        </nav>

        <GlobalSearch />
      </div>
    </header>
  );
}

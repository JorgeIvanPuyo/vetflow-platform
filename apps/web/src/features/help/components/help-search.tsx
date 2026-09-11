import { Search } from "lucide-react";

export function HelpSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div role="search" className="help-search">
      <label className="field" htmlFor="help-search"><span>Buscar una guía</span></label>
      <div className="help-search-control">
        <Search aria-hidden="true" size={20} />
        <input id="help-search" type="search" placeholder="¿Qué necesitas hacer?" value={value} onChange={(event) => onChange(event.target.value)} aria-controls="help-results" />
      </div>
    </div>
  );
}

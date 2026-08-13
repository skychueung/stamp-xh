import { Atom, ExternalLink } from "lucide-react";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 h-16 bg-white border-b border-slate-200">
      <div className="mx-auto max-w-7xl px-6 h-full flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Atom className="h-6 w-6 text-slate-900" />
          <span className="text-lg font-semibold text-slate-900 tracking-tight">
            Peptide Filter Pipeline
          </span>
        </div>
        <nav className="flex items-center gap-4">
          <a
            href="#"
            className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 transition-colors"
          >
            Docs
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <a
            href="#"
            className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 transition-colors"
          >
            Demo
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <a
            href="#"
            className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 transition-colors"
          >
            GitHub
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </nav>
      </div>
    </header>
  );
}

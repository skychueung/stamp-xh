import { SiteHeader } from "@/components/layout/SiteHeader";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { HeroSection } from "@/components/hero/HeroSection";
import { InputConsolePanel } from "@/components/input-console/InputConsolePanel";
import { ResultsPanel } from "@/components/results/ResultsPanel";
import { PipelineSection } from "@/components/pipeline/PipelineSection";
import { ResultsSnapshotSection } from "@/components/snapshot/ResultsSnapshotSection";
import { CandidateDetailDrawer } from "@/components/drawers/CandidateDetailDrawer";
import { CandidateCompareDrawer } from "@/components/drawers/CandidateCompareDrawer";
import { ErrorBanner } from "@/components/status/ErrorBanner";
import { ApiWarmupBanner } from "@/components/status/ApiWarmupBanner";
import { LoadingOverlay } from "@/components/status/LoadingOverlay";

export default function PeptideFilterPage() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <SiteHeader />
      {/* Platform Banner */}
      <div className="bg-amber-50 border-b border-amber-200">
        <div className="mx-auto max-w-7xl px-6 py-2 flex items-center gap-2">
          <span className="inline-flex items-center rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700 uppercase tracking-wide">
            STAMP v0.6d-P2a
          </span>
          <p className="text-xs text-amber-800">
            靶向肽智能筛选平台 — 计算预测结果，未经实验验证。
          </p>
        </div>
      </div>
      <main className="mx-auto max-w-7xl px-6 py-8 space-y-8">
        <HeroSection />
        <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="xl:col-span-5">
            <InputConsolePanel />
          </div>
          <div className="xl:col-span-7">
            <ResultsPanel />
          </div>
        </section>
        <ApiWarmupBanner />
        <ErrorBanner />
        <PipelineSection />
        <ResultsSnapshotSection />
      </main>
      <CandidateDetailDrawer />
      <CandidateCompareDrawer />
      <LoadingOverlay />
      <SiteFooter />
    </div>
  );
}

// P33U-D23A: /targeted-peptide-design now renders the D20A-D23 Run Console.
// The old P2 skeleton form (targetPeptideDesignApi.createJob — broken, returned
// "API request failed") has been replaced. The Run Console calls the real dev
// APIs: POST /api/v1/p33u/run/model and POST /api/v1/p33u/run/scorer.
//
// Dev-only. Results are computational predictions and require experimental
// validation. PPFlow is never invoked. Prod 8001/8080 untouched.
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { RunConsole } from '@/components/p33u/RunConsole';

export default function TargetedPeptideDesignPage() {
  return (
    <PlatformLayout>
      <div className="space-y-6 pb-12">
        <RunConsole />
      </div>
    </PlatformLayout>
  );
}

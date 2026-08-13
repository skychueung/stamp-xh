import { Routes, Route, Navigate, useLocation } from 'react-router';
import { Suspense, lazy } from 'react';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { Sidebar } from '@/components/platform/Sidebar';
import HomePage from '@/pages/HomePage';
import TargetingPeptidePage from '@/pages/TargetingPeptidePage';
import PipelineOrchestratorPage from '@/pages/PipelineOrchestratorPage';
import StructureViewerPage from '@/pages/StructureViewerPage';
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import ChangePasswordPage from '@/pages/ChangePasswordPage';
import ForbiddenPage from '@/pages/ForbiddenPage';

const ProjectDashboardPage = lazy(() => import('@/pages/ProjectDashboardPage'));
const TargetProteinInputPage = lazy(() => import('@/pages/TargetProteinInputPage'));
const EpitopeScreeningPage = lazy(() => import('@/pages/EpitopeScreeningPage'));
const PeptideGenerationPage = lazy(() => import('@/pages/PeptideGenerationPage'));
const PeptideOptimizationPage = lazy(() => import('@/pages/PeptideOptimizationPage'));
const TargetedPeptideDesignPage = lazy(() => import('@/pages/TargetedPeptideDesignPage'));
const StructureValidationPage = lazy(() => import('@/pages/StructureValidationPage'));
const FinalRankingPage = lazy(() => import('@/pages/FinalRankingPage'));
const StampHybridDesignPage = lazy(() => import('@/pages/StampHybridDesignPage'));
const ProjectResultsPage = lazy(() => import('@/pages/ProjectResultsPage'));
const ExperimentalValidationDashboardPage = lazy(() => import('@/pages/ExperimentalValidationDashboardPage'));
const CandidatePrioritizationPage = lazy(() => import('@/pages/CandidatePrioritizationPage'));
const LIMSIntegrationPage = lazy(() => import('@/pages/LIMSIntegrationPage'));
const ProductionMDPage = lazy(() => import('@/pages/ProductionMDPage'));
const BatchComputationPage = lazy(() => import('@/pages/BatchComputationPage'));
const BatchComputationDetailPage = lazy(() => import('@/pages/BatchComputationDetailPage'));
const EvoBind2Page = lazy(() => import('@/pages/EvoBind2Page'));
const JobCenterPage = lazy(() => import('@/pages/JobCenterPage'));
const TargetedPeptideDesignCenterPage = lazy(() => import('@/pages/TargetedPeptideDesignCenterPage'));
const SystemHealthPage = lazy(() => import('@/pages/SystemHealthPage'));
const AuditLogsPage = lazy(() => import('@/pages/AuditLogsPage'));
const FileManagerPage = lazy(() => import('@/pages/FileManagerPage'));
const AdminUsersPage = lazy(() => import('@/pages/AdminUsersPage'));

function LazyWrapper({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen bg-xh-bg ml-[260px]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-xh-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-xh-muted">Loading...</span>
        </div>
      </div>
    }>
      {children}
    </Suspense>
  );
}

function ProtectedRoute({ children, adminOnly }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { user, isLoading, isAdmin } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-xh-bg ml-[260px]">
        <div className="w-8 h-8 border-2 border-xh-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (adminOnly && !isAdmin) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 bg-xh-bg min-w-0 ml-[260px]">{children}</main>
    </div>
  );
}

function RootRoute() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-xh-bg">
        <div className="w-8 h-8 border-2 border-xh-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <AuthenticatedRoutes />;
}

function AuthenticatedRoutes() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/workspaces" element={<LazyWrapper><ProjectDashboardPage /></LazyWrapper>} />
        <Route path="/design" element={<TargetingPeptidePage />} />
        <Route path="/structure" element={<StructureViewerPage />} />
        <Route path="/filter" element={<PipelineOrchestratorPage />} />
        <Route path="/demo" element={<PipelineOrchestratorPage />} />
        <Route path="/target-protein" element={<LazyWrapper><TargetProteinInputPage /></LazyWrapper>} />
        <Route path="/epitope-screening" element={<LazyWrapper><EpitopeScreeningPage /></LazyWrapper>} />
        <Route path="/peptide-generation" element={<LazyWrapper><PeptideGenerationPage /></LazyWrapper>} />
        <Route path="/targeted-peptide-design" element={<LazyWrapper><TargetedPeptideDesignPage /></LazyWrapper>} />
        <Route path="/peptide-optimization" element={<LazyWrapper><PeptideOptimizationPage /></LazyWrapper>} />
        <Route path="/structure-validation" element={<LazyWrapper><StructureValidationPage /></LazyWrapper>} />
        <Route path="/stamp-hybrid-design" element={<LazyWrapper><StampHybridDesignPage /></LazyWrapper>} />
        <Route path="/final-ranking" element={<LazyWrapper><FinalRankingPage /></LazyWrapper>} />
        <Route path="/projects/:projectId/results" element={<LazyWrapper><ProjectResultsPage /></LazyWrapper>} />
        <Route path="/projects/:projectId/experimental-validation" element={<LazyWrapper><ExperimentalValidationDashboardPage /></LazyWrapper>} />
        <Route path="/projects/:projectId/candidate-prioritization" element={<LazyWrapper><CandidatePrioritizationPage /></LazyWrapper>} />
        <Route path="/lims-integration" element={<LazyWrapper><LIMSIntegrationPage /></LazyWrapper>} />
        <Route path="/production-md" element={<LazyWrapper><ProductionMDPage /></LazyWrapper>} />
        <Route path="/batch-computation" element={<LazyWrapper><BatchComputationPage /></LazyWrapper>} />
        <Route path="/batch-computation/:id" element={<LazyWrapper><BatchComputationDetailPage /></LazyWrapper>} />
        <Route
          path="/target-design"
          element={
            <ProtectedRoute>
              <LazyWrapper><TargetedPeptideDesignCenterPage /></LazyWrapper>
            </ProtectedRoute>
          }
        />
        <Route path="/evobind2" element={<LazyWrapper><EvoBind2Page /></LazyWrapper>} />
        <Route path="/job-center" element={<LazyWrapper><JobCenterPage /></LazyWrapper>} />
        <Route path="/system-health" element={<LazyWrapper><SystemHealthPage /></LazyWrapper>} />
        <Route path="/audit-logs" element={<LazyWrapper><AuditLogsPage /></LazyWrapper>} />
        <Route path="/file-manager" element={<LazyWrapper><FileManagerPage /></LazyWrapper>} />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute adminOnly>
              <LazyWrapper><AdminUsersPage /></LazyWrapper>
            </ProtectedRoute>
          }
        />
        <Route path="/403" element={<ForbiddenPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

function PublicRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRoute />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route path="*" element={<AuthenticatedRoutes />} />
    </Routes>
  );
}

export default function App() {
  return (
    <LanguageProvider>
      <AuthProvider>
        <PublicRoutes />
      </AuthProvider>
    </LanguageProvider>
  );
}

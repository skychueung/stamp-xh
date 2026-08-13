import { useState } from 'react';
import { NavLink } from 'react-router';
import {
  Home,
  GitBranch,
  Dna,
  Target,
  Atom,
  FlaskConical,
  Hexagon,
  Trophy,
  Layers,
  Users,
  Mail,
  Plug,
  Activity,
  Briefcase,
  HeartPulse,
  ClipboardList,
  FolderOpen,
  Crown,
  Boxes,
  LogOut,
  User as UserIcon,
  Shield,
  ChevronDown,
  ChevronUp,
  MoreHorizontal,
  Beaker,
  ListOrdered,
} from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';
import { useAuth } from '@/contexts/AuthContext';
import { LanguageToggle } from './LanguageToggle';
import { Button } from '@/components/ui/button';
import { TEXT } from '@/lib/platformText';
import styles from './Sidebar.module.css';

type NavItem = {
  key: string;
  label: string;
  href: string;
  icon: React.ElementType;
  adminOnly?: boolean;
};

export function Sidebar() {
  const { t, isZh } = useLanguage();
  const { user, isAdmin, logout } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);

  // Core navigation (8 items). /filter is the unified 全自动/半自动 workbench.
  const CORE_NAV: NavItem[] = [
    { key: 'home', label: TEXT.sidebar.navHome, href: '/', icon: Home },
    { key: 'auto-design', label: '全自动 / 半自动', href: '/filter', icon: GitBranch },
    { key: 'epitope-screening', label: t.nav.epitopeScreening, href: '/epitope-screening', icon: Target },
    { key: 'peptide-generation', label: t.nav.peptideGeneration, href: '/peptide-generation', icon: Atom },
    { key: 'peptide-optimization', label: t.nav.peptideOptimization, href: '/peptide-optimization', icon: Beaker },
    { key: 'structure-validation', label: t.nav.structureValidation, href: '/structure-validation', icon: Hexagon },
    { key: 'final-ranking', label: t.nav.finalRanking, href: '/final-ranking', icon: ListOrdered },
  ];

  // Golden Run demo mainline (highlighted, kept prominent; must not break ?demo=golden).
  const GOLDEN_NAV: NavItem = {
    key: 'stamp-demo',
    label: 'STAMP 演示主线 · Golden Run',
    href: '/epitope-screening?demo=golden',
    icon: Trophy,
  };

  // Everything else collapsed under 更多工具.
  const MORE_NAV: NavItem[] = [
    { key: 'target-protein', label: '目标蛋白输入（旧版）', href: '/target-protein', icon: Dna },
    { key: 'stamp-hybrid-design', label: t.nav.stampHybridDesign, href: '/stamp-hybrid-design', icon: Layers },
    { key: 'targeted-peptide-design', label: '靶向肽生成中心 (RunConsole) · Dev', href: '/targeted-peptide-design', icon: FlaskConical },
    { key: 'structure-viewer', label: t.nav.structureViewer, href: '/structure', icon: Hexagon },
    { key: 'target-design', label: 'Design Center · Dev', href: '/target-design', icon: FlaskConical },
    { key: 'evobind2', label: 'EvoBind2 · Dev', href: '/evobind2', icon: Atom },
    { key: 'lims-integration', label: 'LIMS / ELN · Dev', href: '/lims-integration', icon: Plug },
    { key: 'production-md', label: 'Production MD · Dev', href: '/production-md', icon: Activity },
    { key: 'batch-computation', label: 'Batch Computation · Dev', href: '/batch-computation', icon: Boxes },
    { key: 'job-center', label: 'Job Center · Dev', href: '/job-center', icon: Briefcase },
    { key: 'system-health', label: 'System Health · Dev', href: '/system-health', icon: HeartPulse },
    { key: 'audit-logs', label: 'Audit Logs · Dev', href: '/audit-logs', icon: ClipboardList, adminOnly: true },
    { key: 'file-manager', label: 'File Manager · Dev', href: '/file-manager', icon: FolderOpen },
  ];

  const visibleMore = MORE_NAV.filter((item) => !item.adminOnly || isAdmin);

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logoContainer}>
        <h1 className={styles.logoPrimary}>{TEXT.sidebar.logoPrimary}</h1>
        <p className={styles.logoSecondary}>{TEXT.sidebar.logoSecondary}</p>
        <h2 className={styles.logoTertiary}>{TEXT.sidebar.logoTertiary}</h2>
        <p className={styles.logoQuaternary}>{TEXT.sidebar.logoQuaternary}</p>
      </div>

      <nav className={styles.nav}>
        {/* Core nav */}
        {CORE_NAV.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.key}
              to={item.href}
              end={item.href === '/'}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
            >
              <Icon className={styles.navIcon} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}

        {/* Golden Run demo mainline */}
        <NavLink
          key={GOLDEN_NAV.key}
          to={GOLDEN_NAV.href}
          className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
        >
          <Trophy className={styles.navIcon} />
          <span>{GOLDEN_NAV.label}</span>
        </NavLink>

        {/* More tools (collapsible) */}
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          className={styles.navLink}
          aria-expanded={moreOpen}
        >
          <MoreHorizontal className={styles.navIcon} />
          <span>更多工具</span>
          {moreOpen ? <ChevronUp className="w-3 h-3 ml-auto opacity-60" /> : <ChevronDown className="w-3 h-3 ml-auto opacity-60" />}
        </button>
        {moreOpen && (
          <div className="ml-2 border-l border-white/10 pl-2 space-y-0.5">
            {visibleMore.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.key}
                  to={item.href}
                  className={({ isActive }) => `${styles.navLink} text-xs ${isActive ? styles.navLinkActive : ''}`}
                >
                  <Icon className={styles.navIcon} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        )}

        {/* Footer-ish links */}
        <NavLink to="/" end className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}>
          <Users className={styles.navIcon} />
          <span>{TEXT.sidebar.navTeam}</span>
        </NavLink>
        <NavLink to="/" end className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}>
          <Mail className={styles.navIcon} />
          <span>{TEXT.sidebar.navContact}</span>
        </NavLink>
        {isAdmin && (
          <NavLink to="/admin/users" className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}>
            <Shield className={styles.navIcon} />
            <span>User management</span>
          </NavLink>
        )}
      </nav>

      <div className="mt-auto px-4 pb-4 space-y-3">
        {user ? (
          <div className="bg-white/5 rounded-lg p-3 border border-white/10 space-y-2">
            <div className="flex items-center gap-2 text-white/90">
              <UserIcon className="w-4 h-4" />
              <span className="text-sm font-medium truncate">{user.username}</span>
            </div>
            <div className="flex items-center gap-2 text-white/60 text-xs">
              {isAdmin ? <Crown className="w-3 h-3 text-amber-400" /> : <UserIcon className="w-3 h-3" />}
              <span className="capitalize">{user.role}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-white border-white/20 hover:bg-white/10 hover:text-white"
              onClick={() => logout()}
            >
              <LogOut className="w-3 h-3 mr-1" />
              Log out
            </Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm" className="flex-1 text-white border-white/20 hover:bg-white/10 hover:text-white">
              <NavLink to="/login">Log in</NavLink>
            </Button>
            <Button asChild size="sm" className="flex-1 bg-xh-primary hover:bg-xh-primary/90">
              <NavLink to="/register">Register</NavLink>
            </Button>
          </div>
        )}
        <LanguageToggle
          variant="outline"
          size="sm"
          className="w-full text-white border-white/20 hover:bg-white/10 hover:text-white"
        />
        <div className="bg-[#156B98]/20 rounded-lg p-3">
          <p className="text-[#156B98] text-xs font-medium">STAMP v1.2-fast</p>
          <p className="text-gray-500 text-[10px] mt-0.5">
            {isZh ? '表位引导靶向肽设计' : 'Epitope-guided targeting peptide design'}
          </p>
        </div>
        <p className="text-[#156B98] text-[10px] text-center font-medium leading-tight">
          {t.footer.disclaimer}
        </p>
      </div>
    </aside>
  );
}

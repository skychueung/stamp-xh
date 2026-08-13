import { useNavigate } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { LanguageToggle } from '@/components/platform/LanguageToggle';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  ArrowRight,
  Dna,
  Microscope,
  Atom,
  Beaker,
  Layers,
  Trophy,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const MODULES = [
  {
    key: 'targetProtein' as const,
    icon: Dna,
    path: '/target-protein',
    color: 'bg-blue-500',
  },
  {
    key: 'epitopeScreening' as const,
    icon: Microscope,
    path: '/epitope-screening',
    color: 'bg-amber-500',
  },
  {
    key: 'peptideGeneration' as const,
    icon: Atom,
    path: '/peptide-generation',
    color: 'bg-emerald-500',
  },
  {
    key: 'peptideOptimization' as const,
    icon: Beaker,
    path: '/peptide-optimization',
    color: 'bg-purple-500',
  },
  {
    key: 'structureValidation' as const,
    icon: Layers,
    path: '/structure-validation',
    color: 'bg-[#156B98]',
  },
  {
    key: 'finalRanking' as const,
    icon: Trophy,
    path: '/final-ranking',
    color: 'bg-rose-500',
  },
];

const FEATURES = [
  { key: 'epitopeDriven' as const, icon: Dna },
  { key: 'aiGeneration' as const, icon: Atom },
  { key: 'validation' as const, icon: Layers },
] as const;

export default function HomePage() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  return (
    <div className="space-y-6 pb-12">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#EFF8FF] via-white to-[#DBEAFE] border border-blue-100 p-5 md:p-6">
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
          {/* Left: title + subtitle + features + buttons */}
          <div className="flex-1 min-w-0">
            <h1 className="text-xl md:text-2xl font-bold text-[#156B98] tracking-tight">
              {t.home.title}
            </h1>
            <p className="mt-1.5 text-sm text-gray-600 max-w-2xl leading-relaxed">
              {t.home.subtitle}
            </p>

            {/* Feature pills */}
            <div className="mt-3 flex flex-wrap gap-2">
              {FEATURES.map((feature) => (
                <span
                  key={feature.key}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#156B98]/10 text-[#156B98] text-xs font-medium"
                >
                  <feature.icon className="w-3.5 h-3.5" />
                  {t.home.features[feature.key]}
                </span>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <Button
                size="sm"
                className="bg-[#156B98] text-white hover:bg-[#125a80] gap-2"
                onClick={() => navigate('/target-protein')}
              >
                {t.home.startButton}
                <ArrowRight className="w-4 h-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-[#156B98]/30 text-[#156B98] hover:bg-[#156B98]/5 gap-2"
                onClick={() => navigate('/structure-validation')}
              >
                {t.home.learnMore}
                <Layers className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Right: Xianghu Lab logo + language toggle */}
          <div className="shrink-0 flex flex-col items-end gap-2">
            <img
              src="/images/home/xianghu_lab_logo.png"
              alt="湘湖实验室 Xianghu Laboratory"
              className="h-auto w-[200px] md:w-[280px] max-w-full object-contain"
              loading="lazy"
            />
            <div className="text-xs text-gray-600 font-medium text-right">
              动物疫病与疫苗团队
            </div>
            <LanguageToggle
              variant="outline"
              size="sm"
              className="border-[#156B98]/20 text-[#156B98] hover:bg-[#156B98]/5"
            />
          </div>
        </div>

        {/* Subtle background decoration */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-blue-200/20 rounded-full -translate-y-1/2 translate-x-1/3 pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-300/10 rounded-full translate-y-1/2 -translate-x-1/3 pointer-events-none" />
      </div>

      {/* Image Cards */}
      <div className="grid md:grid-cols-2 gap-5">
        {/* Team Card */}
        <Card className="border-[#E5E7EB] shadow-sm overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold text-gray-900">
              动物疫病与疫苗团队
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="bg-gray-50 rounded-xl p-2.5">
              <img
                src="/images/home/xianghu_lab_team.png"
                alt="湘湖实验室动物疫病与疫苗团队"
                className="w-full h-auto object-cover rounded-lg max-h-[220px] mx-auto"
                loading="lazy"
              />
            </div>
            <CardDescription className="text-xs text-gray-600 leading-relaxed">
              聚焦动物疫病防控与疫苗/抗菌肽研发，提供靶向肽设计、候选分子筛选、结构验证、MD 稳定性分析、FlexPepDock 对接和 MM-GBSA 能量评估等服务。
            </CardDescription>
          </CardContent>
        </Card>

        {/* STAMP Concept Card */}
        <Card className="border-[#E5E7EB] shadow-sm overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold text-gray-900">
              STAMP 基本结构示意
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="bg-gray-50 rounded-xl p-2.5">
              <img
                src="/images/home/stamp_concept_flow.png"
                alt="STAMP 基本结构示意"
                className="w-full h-auto object-contain rounded-lg max-h-[220px] mx-auto"
                loading="lazy"
              />
            </div>
            <CardDescription className="text-xs text-gray-600 leading-relaxed">
              STAMP 由靶向识别模块、连接子模块和功能多肽模块组成，支持三段式结构设计，从靶标输入到结构验证和计算报告导出的完整设计流程。
            </CardDescription>
          </CardContent>
        </Card>
      </div>

      {/* Pipeline Overview */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          {t.nav.pipeline}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {MODULES.map((module) => (
            <Card
              key={module.key}
              className="cursor-pointer hover:shadow-md transition-shadow border-[#E5E7EB]"
              onClick={() => navigate(module.path)}
            >
              <CardHeader className="pb-2">
                <div
                  className={cn(
                    'w-9 h-9 rounded-lg flex items-center justify-center text-white',
                    module.color
                  )}
                >
                  <module.icon className="w-4 h-4" />
                </div>
              </CardHeader>
              <CardContent>
                <CardTitle className="text-sm">
                  {t.home.modules[module.key].title}
                </CardTitle>
                <CardDescription className="text-xs mt-1 line-clamp-2">
                  {t.home.modules[module.key].desc}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useProject } from '@/contexts/ProjectContext';
import { projectsApi } from '@/lib/api/projects';
import type { Project } from '@/types/project';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import {
  FolderOpen,
  Plus,
  Clock,
  Activity,
  ChevronRight,
  Loader2,
  TestTube2,
} from 'lucide-react';

export default function ProjectDashboardPage() {
  const navigate = useNavigate();
  const { setCurrentProject } = useProject();

  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  // 新建项目表单状态
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');

  // 加载时获取项目列表
  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      setIsLoading(true);
      const data = await projectsApi.list();
      setProjects(data);
    } catch (error) {
      console.error('Failed to fetch projects:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // 选择项目并进入靶向肽输入页
  const handleSelectProject = (project: Project) => {
    setCurrentProject(project);
    navigate('/target-protein');
  };

  // 创建新项目
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;

    try {
      setIsCreating(true);
      const newProject = await projectsApi.create({
        name: newProjectName,
        description: newProjectDesc,
        project_type: 'stamp_design',
      });

      // 创建成功后自动选中并跳转
      handleSelectProject(newProject);
    } catch (error) {
      console.error('Failed to create project:', error);
      alert('Failed to create project. Please check backend connection.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Activity className="w-6 h-6 text-xh-primary" />
            STAMP Workspaces
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Select an existing experiment or create a new workspace to begin targeted peptide design.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* 左侧/上方新建项目卡片 */}
          <div className="md:col-span-1">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sticky top-6">
              <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <Plus className="w-4 h-4" /> Create New Workspace
              </h2>
              <form onSubmit={handleCreateProject} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Project Name *</label>
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    placeholder="e.g., OprF Targeting Exp 01"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Description (Optional)</label>
                  <textarea
                    value={newProjectDesc}
                    onChange={(e) => setNewProjectDesc(e.target.value)}
                    placeholder="Notes about this experiment..."
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none min-h-[80px]"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isCreating || !newProjectName.trim()}
                  className="w-full flex items-center justify-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTube2 className="w-4 h-4" />}
                  Initialize Workspace
                </button>
              </form>
            </div>
          </div>

          {/* 右侧/下方历史项目列表 */}
          <div className="md:col-span-2">
            <h2 className="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <FolderOpen className="w-4 h-4" /> Recent Workspaces
            </h2>

            {isLoading ? (
              <div className="flex items-center justify-center py-12 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : projects.length === 0 ? (
              <div className="text-center py-12 bg-slate-50 border border-slate-200 border-dashed rounded-xl">
                <FolderOpen className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No workspaces found. Create one to get started.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {projects.map((project) => (
                  <div
                    key={project.id}
                    onClick={() => handleSelectProject(project)}
                    className="group bg-white border border-slate-200 hover:border-xh-primary/50 hover:shadow-md transition-all rounded-xl p-4 cursor-pointer flex items-center justify-between"
                  >
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 group-hover:text-xh-primary transition-colors">
                        {project.name}
                      </h3>
                      {project.description && (
                        <p className="text-xs text-slate-500 mt-1 line-clamp-1">
                          {project.description}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-400 font-mono">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(project.updated_at).toLocaleDateString()}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                          {project.project_type || 'Unknown'}
                        </span>
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-xh-primary transform group-hover:translate-x-1 transition-all" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}

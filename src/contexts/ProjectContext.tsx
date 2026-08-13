import React, { createContext, useContext, useState, useEffect } from 'react';
import type { Project } from '@/types/project';
import { projectsApi } from '@/lib/api/projects';

const PROJECT_LS_KEY = 'stamp.currentProjectId.v0.8';

interface ProjectContextType {
  currentProject: Project | null;
  setCurrentProject: (project: Project | null) => void;
  isLoading: boolean;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 初始化加载
  useEffect(() => {
    const initializeProject = async () => {
      const savedProjectId = localStorage.getItem(PROJECT_LS_KEY);

      if (savedProjectId) {
        try {
          const project = await projectsApi.getById(savedProjectId);
          setCurrentProject(project);
        } catch (error) {
          console.error('Failed to restore project from v0.8 storage:', error);
          localStorage.removeItem(PROJECT_LS_KEY);
        }
      }
      setIsLoading(false);
    };

    initializeProject();
  }, []);

  const handleSetProject = (project: Project | null) => {
    setCurrentProject(project);
    if (project) {
      localStorage.setItem(PROJECT_LS_KEY, project.id);
    } else {
      localStorage.removeItem(PROJECT_LS_KEY);
    }
  };

  return (
    <ProjectContext.Provider
      value={{
        currentProject,
        setCurrentProject: handleSetProject,
        isLoading,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (context === undefined) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
}

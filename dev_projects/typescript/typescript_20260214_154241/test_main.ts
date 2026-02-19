import { JiraClient } from 'jira-client';
import { Project } from './models/Project';

describe('JiraClient', () => {
  let jira: JiraClient;

  beforeEach(() => {
    jira = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'your-username',
      password: 'your-password'
    });
  });

  describe('getProjects', () => {
    it('should return a list of projects', async () => {
      const projects = await jira.getProjects();
      expect(projects.length).toBeGreaterThan(0);
    });

    it('should throw an error if the request fails', async () => {
      jest.spyOn(jira, 'getProjects').mockRejectedValue(new Error('Network error'));
      try {
        await jira.getProjects();
      } catch (error) {
        expect(error.message).toBe('Network error');
      }
    });
  });

  describe('createProject', () => {
    it('should create a new project', async () => {
      const newProject: Project = {
        key: 'NEWPROJ',
        name: 'New Project',
        description: 'This is a new project for testing TypeScript integration'
      };
      await jira.createProject(newProject);
      expect(jira.projects).toContainEqual(newProject);
    });

    it('should throw an error if the request fails', async () => {
      jest.spyOn(jira, 'createProject').mockRejectedValue(new Error('Network error'));
      try {
        await jira.createProject({ key: 'NEWPROJ' });
      } catch (error) {
        expect(error.message).toBe('Network error');
      }
    });

    it('should throw an error if the project already exists', async () => {
      const newProject = {
        key: 'NEWPROJ',
        name: 'New Project',
        description: 'This is a new project for testing TypeScript integration'
      };
      await jira.createProject(newProject);
      try {
        await jira.createProject(newProject);
      } catch (error) {
        expect(error.message).toBe('Project already exists');
      }
    });
  });

  describe('updateProject', () => {
    it('should update an existing project', async () => {
      const updatedProject = {
        key: 'NEWPROJ',
        name: 'Updated Project',
        description: 'This project has been updated with TypeScript integration'
      };
      await jira.updateProject(updatedProject);
      expect(jira.projects).toContainEqual(updatedProject);
    });

    it('should throw an error if the request fails', async () => {
      jest.spyOn(jira, 'updateProject').mockRejectedValue(new Error('Network error'));
      try {
        await jira.updateProject({ key: 'NEWPROJ' });
      } catch (error) {
        expect(error.message).toBe('Network error');
      }
    });

    it('should throw an error if the project does not exist', async () => {
      const updatedProject = {
        key: 'NEWPROJ',
        name: 'Updated Project',
        description: 'This project has been updated with TypeScript integration'
      };
      try {
        await jira.updateProject(updatedProject);
      } catch (error) {
        expect(error.message).toBe('Project not found');
      }
    });
  });

  describe('deleteProject', () => {
    it('should delete an existing project', async () => {
      await jira.deleteProject('NEWPROJ');
      expect(jira.projects).not.toContainEqual({ key: 'NEWPROJ' });
    });

    it('should throw an error if the request fails', async () => {
      jest.spyOn(jira, 'deleteProject').mockRejectedValue(new Error('Network error'));
      try {
        await jira.deleteProject('NEWPROJ');
      } catch (error) {
        expect(error.message).toBe('Network error');
      }
    });

    it('should throw an error if the project does not exist', async () => {
      try {
        await jira.deleteProject('NEWPROJ');
      } catch (error) {
        expect(error.message).toBe('Project not found');
      }
    });
  });
});
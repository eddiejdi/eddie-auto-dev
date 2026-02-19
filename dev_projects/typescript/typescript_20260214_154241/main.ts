import { JiraClient } from 'jira-client';
import { Project } from './models/Project';

const jira = new JiraClient({
  url: 'https://your-jira-instance.atlassian.net',
  username: 'your-username',
  password: 'your-password'
});

async function main() {
  try {
    // Listar projetos
    const projects = await jira.getProjects();
    console.log('Projetos:');
    projects.forEach(project => {
      console.log(`- ${project.key}: ${project.name}`);
    });

    // Criar um novo projeto
    const newProject: Project = {
      key: 'NEWPROJ',
      name: 'New Project',
      description: 'This is a new project for testing TypeScript integration'
    };
    await jira.createProject(newProject);
    console.log(`Projeto criado com chave ${newProject.key}`);

    // Atualizar um projeto
    const updatedProject = {
      key: 'NEWPROJ',
      name: 'Updated Project',
      description: 'This project has been updated with TypeScript integration'
    };
    await jira.updateProject(updatedProject);
    console.log(`Projeto atualizado com chave ${updatedProject.key}`);

    // Excluir um projeto
    await jira.deleteProject('NEWPROJ');
    console.log(`Projeto excluído com chave NEWPROJ`);

  } catch (error) {
    console.error('Erro:', error);
  }
}

main();
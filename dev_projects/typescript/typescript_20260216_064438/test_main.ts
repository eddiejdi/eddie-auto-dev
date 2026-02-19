import axios from 'axios';
import { expect } from 'chai';

// Define a interface para representar uma atividade do projeto
interface Activity {
  id: number;
  title: string;
  description: string;
}

// Define a classe para representar um projeto
class Project {
  private name: string;
  private activities: Activity[];

  constructor(name: string) {
    this.name = name;
    this.activities = [];
  }

  addActivity(activity: Activity): void {
    this.activities.push(activity);
  }

  getActivities(): Activity[] {
    return this.activities;
  }
}

// Define a classe para representar o sistema de tipos avançado
class TypeSystem {
  // Implementação do sistema de tipos avançado aqui
}

// Define a classe para representar uma integração com Jira
class JiraIntegration {
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async createIssue(projectName: string, activityTitle: string, description: string): Promise<void> {
    try {
      const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', {
        fields: {
          project: { key: projectName },
          summary: activityTitle,
          description: description,
          issuetype: { name: 'Task' }
        }
      });

      console.log(`Issue created with ID: ${response.data.id}`);
    } catch (error) {
      console.error('Error creating issue:', error);
    }
  }

  async getIssues(projectName: string): Promise<Activity[]> {
    try {
      const response = await axios.get(`https://your-jira-instance.atlassian.net/rest/api/2/search?jql=project=${projectName}&fields=id,title,description`);
      return response.data.issues.map(issue => ({
        id: issue.id,
        title: issue.fields.title,
        description: issue.fields.description
      }));
    } catch (error) {
      console.error('Error fetching issues:', error);
      return [];
    }
  }
}

// Implementação da função main()
async function main() {
  const apiKey = 'your-jira-api-key';
  const jiraIntegration = new JiraIntegration(apiKey);

  // Criar um projeto
  const project = new Project('My TypeScript Project');
  project.addActivity({ id: 1, title: 'Create typescript agent', description: 'Implement a TypeScript agent for tracking activities in typescript.' });
  project.addActivity({ id: 2, title: 'Integrate with Jira', description: 'Integrate the TypeScript agent with Jira to track activities.' });

  // Cadastrar atividades no Jira
  await jiraIntegration.createIssue(project.name, 'Create typescript agent', project.getActivities().map(activity => activity.title));
  await jiraIntegration.createIssue(project.name, 'Integrate with Jira', project.getActivities().map(activity => activity.title));

  // Listar atividades do projeto no Jira
  const issues = await jiraIntegration.getIssues(project.name);
  console.log('List of activities in the project:', issues.map(issue => issue.title));
}

// Executar a função main()
main();

describe('JiraIntegration', () => {
  describe('createIssue', () => {
    it('should create an issue with valid inputs', async () => {
      const apiKey = 'your-jira-api-key';
      const jiraIntegration = new JiraIntegration(apiKey);
      const projectName = 'My TypeScript Project';
      const activityTitle = 'Create typescript agent';
      const description = 'Implement a TypeScript agent for tracking activities in typescript.';
      await jiraIntegration.createIssue(projectName, activityTitle, description);
    });

    it('should throw an error if the project name is invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const jiraIntegration = new JiraIntegration(apiKey);
      const projectName = '';
      const activityTitle = 'Create typescript agent';
      const description = 'Implement a TypeScript agent for tracking activities in typescript.';
      await expect(jiraIntegration.createIssue(projectName, activityTitle, description)).to.be.rejectedWith('Invalid project name');
    });

    it('should throw an error if the activity title is invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const jiraIntegration = new JiraIntegration(apiKey);
      const projectName = 'My TypeScript Project';
      const activityTitle = '';
      const description = 'Implement a TypeScript agent for tracking activities in typescript.';
      await expect(jiraIntegration.createIssue(projectName, activityTitle, description)).to.be.rejectedWith('Invalid activity title');
    });

    it('should throw an error if the description is invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const jiraIntegration = new JiraIntegration(apiKey);
      const projectName = 'My TypeScript Project';
      const activityTitle = 'Create typescript agent';
      const description = '';
      await expect(jiraIntegration.createIssue(projectName, activityTitle, description)).to.be.rejectedWith('Invalid description');
    });
  });

  describe('getIssues', () => {
    it('should return issues with valid inputs', async () => {
      const apiKey = 'your-jira-api-key';
      const jiraIntegration = new JiraIntegration(apiKey);
      const projectName = 'My TypeScript Project';
      await jiraIntegration.createIssue(projectName, 'Create typescript agent', project.getActivities().map(activity => activity.title));
      await jiraIntegration.createIssue(projectName, 'Integrate with Jira', project.getActivities().map(activity => activity.title));
      const issues = await jiraIntegration.getIssues(projectName);
      expect(issues.length).to.equal(2);
    });

    it('should throw an error if the project name is invalid', async () => {
      const apiKey = 'your-jira-api-key';
      const jiraIntegration = new JiraIntegration(apiKey);
      const projectName = '';
      await expect(jiraIntegration.getIssues(projectName)).to.be.rejectedWith('Invalid project name');
    });
  });
});
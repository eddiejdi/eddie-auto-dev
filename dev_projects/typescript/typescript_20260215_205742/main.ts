import { JiraClient } from 'jira-client';
import { TestRunner } from './TestRunner';
import { BuildManager } from './BuildManager';
import { DeploymentManager } from './DeploymentManager';

class Scrum10 {
  private jiraClient: JiraClient;
  private testRunner: TestRunner;
  private buildManager: BuildManager;
  private deploymentManager: DeploymentManager;

  constructor(jiraToken: string, jiraUrl: string) {
    this.jiraClient = new JiraClient({
      auth: { token: jiraToken },
      url: jiraUrl,
    });

    this.testRunner = new TestRunner();
    this.buildManager = new BuildManager();
    this.deploymentManager = new DeploymentManager();
  }

  async executeScrum10() {
    try {
      // Integração com Jira
      const issues = await this.jiraClient.searchIssues({
        jql: 'project = SCRUM AND status = In Progress',
      });

      console.log('Issues in progress:', issues);

      // Automatização de testes
      await this.testRunner.runTests();

      // Gerenciamento de builds
      await this.buildManager.manageBuilds();

      // Deploy automático
      await this.deploymentManager.deploy();
    } catch (error) {
      console.error('Error executing Scrum 10:', error);
    }
  }

  static main() {
    const jiraToken = 'your-jira-token';
    const jiraUrl = 'https://your-jira-url.atlassian.net';

    const scrum10 = new Scrum10(jiraToken, jiraUrl);
    scrum10.executeScrum10();
  }
}

Scrum10.main();
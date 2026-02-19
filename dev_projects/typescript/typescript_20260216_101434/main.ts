import { JiraClient } from 'jira-client';
import { Agent } from 'typescript-agent';

class JiraScrum10 {
  private jiraClient: JiraClient;
  private agent: Agent;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      url: jiraUrl,
      auth: { username, password }
    });
    this.agent = new Agent();
  }

  async startScrum10() {
    try {
      await this.authenticate();
      await this.createProject();
      await this.addTeamMembers();
      await this.startSprint();
      await this.trackIssues();
    } catch (error) {
      console.error('Error:', error);
    }
  }

  private async authenticate() {
    const token = await this.jiraClient.auth.login();
    this.agent.setToken(token);
  }

  private async createProject() {
    const projectData = {
      name: 'Scrum10 Project',
      key: 'SCRUM10'
    };
    const project = await this.jiraClient.createProject(projectData);
    console.log('Project created:', project);
  }

  private async addTeamMembers() {
    const teamMembers = ['user1', 'user2', 'user3'];
    for (const member of teamMembers) {
      await this.jiraClient.addUserToProject(member, 'SCRUM10');
    }
    console.log('Team members added to project.');
  }

  private async startSprint() {
    const sprintData = {
      name: 'Scrum10 Sprint',
      startDate: new Date(),
      endDate: new Date(new Date().getTime() + 7 * 24 * 60 * 60 * 1000)
    };
    const sprint = await this.jiraClient.createSprint(sprintData, 'SCRUM10');
    console.log('Sprint created:', sprint);
  }

  private async trackIssues() {
    const issues = [
      { key: 'ISSUE1', status: 'In Progress' },
      { key: 'ISSUE2', status: 'To Do' }
    ];

    for (const issue of issues) {
      await this.jiraClient.updateIssueStatus(issue.key, issue.status);
      console.log(`Issue ${issue.key} updated to ${issue.status}.`);
    }
  }

  static async main() {
    const jiraUrl = 'https://your-jira-instance.atlassian.net';
    const username = 'your-username';
    const password = 'your-password';

    const scrum10 = new JiraScrum10(jiraUrl, username, password);
    await scrum10.startScrum10();
  }
}

if (require.main === module) {
  JiraScrum10.main().catch(error => console.error('Error:', error));
}
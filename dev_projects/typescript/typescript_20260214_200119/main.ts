import { JiraClient } from 'jira-client';
import { Task } from './Task';

class ScrumTeam {
  private jira: JiraClient;
  private tasks: Task[];

  constructor(jira: JiraClient) {
    this.jira = jira;
    this.tasks = [];
  }

  async addTask(task: Task): Promise<void> {
    try {
      await this.jira.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: task.summary,
          description: task.description,
          issuetype: { name: 'Bug' }
        }
      });
      console.log(`Task added to Jira: ${task.summary}`);
      this.tasks.push(task);
    } catch (error) {
      console.error('Error adding task:', error);
    }
  }

  async updateTask(taskId: string, newSummary: string): Promise<void> {
    try {
      await this.jira.updateIssue({
        issueKey: taskId,
        fields: { summary: newSummary }
      });
      console.log(`Task updated in Jira: ${newSummary}`);
    } catch (error) {
      console.error('Error updating task:', error);
    }
  }

  async deleteTask(taskId: string): Promise<void> {
    try {
      await this.jira.deleteIssue({ issueKey: taskId });
      console.log(`Task deleted from Jira: ${taskId}`);
    } catch (error) {
      console.error('Error deleting task:', error);
    }
  }

  async listTasks(): Promise<Task[]> {
    try {
      const issues = await this.jira.searchIssues({
        jql: 'project=YOUR_PROJECT_KEY',
        fields: ['summary', 'description']
      });
      return issues.map(issue => new Task(issue.key, issue.fields.summary, issue.fields.description));
    } catch (error) {
      console.error('Error listing tasks:', error);
      return [];
    }
  }

  async main(): Promise<void> {
    const jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'YOUR_USERNAME',
      password: 'YOUR_PASSWORD'
    });

    const scrumTeam = new ScrumTeam(jiraClient);

    try {
      await scrumTeam.addTask(new Task('T100', 'Fix bug in login page', 'Ensure user can log in with correct credentials'));
      await scrumTeam.updateTask('T100', 'Update login page to use HTTPS');
      await scrumTeam.deleteTask('T100');
    } catch (error) {
      console.error('Error running main:', error);
    }
  }
}

class Task {
  constructor(public key: string, public summary: string, public description: string) {}
}
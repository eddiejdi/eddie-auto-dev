import { JiraClient } from 'jira-client';
import { Task } from './Task';

class Scrum10 {
  private jiraClient: JiraClient;
  private tasks: Task[];

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      url: jiraUrl,
      auth: { username, password }
    });
    this.tasks = [];
  }

  async fetchTasks(): Promise<void> {
    const issues = await this.jiraClient.searchIssues({
      jql: 'project = YOUR_PROJECT_KEY AND status = Open'
    });

    for (const issue of issues.issues) {
      const task = new Task(issue.key, issue.fields.summary);
      this.tasks.push(task);
    }
  }

  async monitorTasks(): Promise<void> {
    while (true) {
      await this.fetchTasks();

      // Simulate task completion
      for (let i = 0; i < this.tasks.length; i++) {
        if (Math.random() < 0.5) {
          this.tasks[i].complete();
        }
      }

      console.log('Tasks:', this.tasks.map(task => task.status));

      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }

  async main(): Promise<void> {
    try {
      await this.fetchTasks();
      await this.monitorTasks();
    } catch (error) {
      console.error('Error:', error);
    }
  }
}

// Example usage
const scrum10 = new Scrum10('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
scrum10.main();
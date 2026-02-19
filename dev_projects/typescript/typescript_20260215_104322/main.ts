import { JiraClient } from 'jira-client';
import { Project, Issue, Comment } from 'jira-client/types';

// Define a classe para representar um projeto no sistema de Jira
class JiraProject {
  private project: Project;

  constructor(project: Project) {
    this.project = project;
  }

  getSummary(): string {
    return `Project ID: ${this.project.id}, Name: ${this.project.name}`;
  }
}

// Define a classe para representar uma tarefa no sistema de Jira
class JiraIssue {
  private issue: Issue;

  constructor(issue: Issue) {
    this.issue = issue;
  }

  getSummary(): string {
    return `Issue ID: ${this.issue.id}, Summary: ${this.issue.fields.summary}`;
  }
}

// Define a classe para representar um comentário no sistema de Jira
class JiraComment {
  private comment: Comment;

  constructor(comment: Comment) {
    this.comment = comment;
  }

  getSummary(): string {
    return `Comment ID: ${this.comment.id}, Text: ${this.comment.fields.body}`;
  }
}

// Define a classe para representar o sistema de Jira
class JiraSystem {
  private client: JiraClient;

  constructor(url: string, token: string) {
    this.client = new JiraClient({
      url,
      auth: { username: 'your-username', password: 'your-password' }
    });
  }

  async getProject(projectId: string): Promise<JiraProject> {
    const project = await this.client.getProject(projectId);
    return new JiraProject(project);
  }

  async getIssue(issueId: string): Promise<JiraIssue> {
    const issue = await this.client.getIssue(issueId);
    return new JiraIssue(issue);
  }

  async createComment(issueId: string, commentText: string): Promise<void> {
    const comment = await this.client.createComment({
      issueKey: issueId,
      body: commentText
    });
    console.log(`Comment created: ${comment.id}`);
  }
}

// Função main para executar o sistema de Jira
async function main() {
  const url = 'https://your-jira-instance.atlassian.net';
  const token = 'your-jira-token';

  const jiraSystem = new JiraSystem(url, token);

  try {
    // Get a project by ID
    const projectId = 'YOUR_PROJECT_ID';
    const project = await jiraSystem.getProject(projectId);
    console.log(`Project: ${project.getSummary()}`);

    // Get an issue by ID
    const issueId = 'YOUR_ISSUE_ID';
    const issue = await jiraSystem.getIssue(issueId);
    console.log(`Issue: ${issue.getSummary()}`);

    // Create a comment on the issue
    const commentText = 'This is a test comment.';
    await jiraSystem.createComment(issueId, commentText);

    console.log('All operations completed successfully.');
  } catch (error) {
    console.error('An error occurred:', error);
  }
}

// Execute the main function if this file is run as a script
if (require.main === module) {
  main();
}
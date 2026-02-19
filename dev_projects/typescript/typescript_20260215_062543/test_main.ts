import axios from 'axios';
import { JiraIssue } from './JiraIssue';

interface JiraClient {
  createIssue(issue: JiraIssue): Promise<JiraIssue>;
  updateIssue(issueId: string, issue: Partial<JiraIssue>): Promise<JiraIssue>;
}

class JiraService implements JiraClient {
  private apiUrl = 'https://your-jira-instance.atlassian.net/rest/api/2';

  async createIssue(issue: JiraIssue): Promise<JiraIssue> {
    const response = await axios.post(`${this.apiUrl}/issue`, issue);
    return response.data;
  }

  async updateIssue(issueId: string, issue: Partial<JiraIssue>): Promise<JiraIssue> {
    const response = await axios.put(`${this.apiUrl}/issue/${issueId}`, issue);
    return response.data;
  }
}

class JiraIssue {
  constructor(
    public key: string,
    public summary: string,
    public description: string,
    public priority: string,
    public status: string
  ) {}
}

async function main() {
  const jiraService = new JiraService();

  try {
    const issue = new JiraIssue(
      'TC-100',
      'Implement SCRUM-10 in TypeScript',
      'This is a test case for the SCRUM-10 implementation in TypeScript.',
      'High',
      'To Do'
    );

    const createdIssue = await jiraService.createIssue(issue);
    console.log('Created Issue:', createdIssue);

    // Update the issue
    const updatedIssue = new JiraIssue(
      createdIssue.key,
      'Implement SCRUM-10 in TypeScript',
      'This is a test case for the SCRUM-10 implementation in TypeScript.',
      'High',
      'In Progress'
    );

    await jiraService.updateIssue(createdIssue.key, updatedIssue);
    console.log('Updated Issue:', updatedIssue);

    // Delete the issue
    await jiraService.deleteIssue(createdIssue.key);
    console.log('Deleted Issue');
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}
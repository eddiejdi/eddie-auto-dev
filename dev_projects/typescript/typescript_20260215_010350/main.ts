import axios from 'axios';

interface JiraIssue {
  key: string;
  summary: string;
  description: string;
}

class JiraClient {
  private apiUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  async getIssue(issueKey: string): Promise<JiraIssue> {
    const response = await axios.get(`${this.apiUrl}/issue/${issueKey}`, {
      headers: { Authorization: `Bearer ${this.token}` },
    });

    return response.data as JiraIssue;
  }
}

class ScrumBoard {
  private issues: JiraIssue[];

  constructor() {
    this.issues = [];
  }

  async addIssue(issueKey: string, summary: string, description: string): Promise<void> {
    const issueData = { key: issueKey, summary, description };
    await axios.post(`${this.apiUrl}/issue`, issueData, {
      headers: { Authorization: `Bearer ${this.token}` },
    });

    this.issues.push(issueData);
  }

  async updateIssue(issueKey: string, summary: string, description: string): Promise<void> {
    const updatedIssueData = { key: issueKey, summary, description };
    await axios.put(`${this.apiUrl}/issue/${issueKey}`, updatedIssueData, {
      headers: { Authorization: `Bearer ${this.token}` },
    });

    this.issues.forEach((issue) => {
      if (issue.key === issueKey) {
        issue.summary = summary;
        issue.description = description;
      }
    });
  }

  async deleteIssue(issueKey: string): Promise<void> {
    await axios.delete(`${this.apiUrl}/issue/${issueKey}`, {
      headers: { Authorization: `Bearer ${this.token}` },
    });

    this.issues = this.issues.filter((issue) => issue.key !== issueKey);
  }
}

async function main() {
  const token = 'your-jira-token';
  const jiraClient = new JiraClient(token);

  const scrumBoard = new ScrumBoard();

  try {
    await scrumBoard.addIssue('ABC-123', 'New feature implementation', 'Implement the new feature in the application');
    console.log('Issue added successfully');

    await scrumBoard.updateIssue('ABC-123', 'Updated feature implementation', 'Update the feature implementation to include new features');
    console.log('Issue updated successfully');

    await scrumBoard.deleteIssue('ABC-123');
    console.log('Issue deleted successfully');
  } catch (error) {
    console.error('Error:', error);
  }
}

if (require.main === module) {
  main();
}
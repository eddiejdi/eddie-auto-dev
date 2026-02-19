import axios from 'axios';

interface JiraIssue {
  key: string;
  summary: string;
  status: string;
}

class JiraClient {
  private apiUrl = 'https://your-jira-instance.atlassian.net/rest/api/3';
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  async getIssue(key: string): Promise<JiraIssue> {
    const response = await axios.get(`${this.apiUrl}/issue/${key}`, {
      headers: {
        'Authorization': `Basic ${Buffer.from(`${this.token}:x`).toString('base64')}`,
      },
    });

    return response.data;
  }
}

async function main() {
  const token = 'your-jira-token';
  const jiraClient = new JiraClient(token);

  try {
    const issue = await jiraClient.getIssue('YOUR-ISSUE-KEY');
    console.log(`Issue: ${issue.summary}`);
    console.log(`Status: ${issue.status}`);
  } catch (error) {
    console.error('Error fetching issue:', error);
  }
}

if (require.main === module) {
  main();
}
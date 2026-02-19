import { JiraClient } from 'jira-client';
import * as config from './config';

const jira = new JiraClient(config);

async function main() {
  try {
    const issues = await jira.searchIssues({
      jql: 'project = SCRUM-10 AND status = Open',
      fields: ['summary', 'assignee']
    });

    console.log('Open issues:');
    issues.forEach(issue => {
      console.log(`Issue ID: ${issue.id}, Summary: ${issue.fields.summary}`);
    });
  } catch (error) {
    console.error('Error fetching issues:', error);
  }
}

if (require.main === module) {
  main();
}
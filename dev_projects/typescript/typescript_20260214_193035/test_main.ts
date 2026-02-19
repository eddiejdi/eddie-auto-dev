import { JiraClient } from 'jira-client';
import { Activity } from './Activity';

describe('JiraClient', () => {
  describe('createIssue', () => {
    it('should create an issue with valid fields', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      const activity = new Activity(123, 'New TypeScript Activity');
      await createActivity(activity);

      // Add assertions to check the response or any other relevant data
    });

    it('should throw an error if fields are missing', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      await expect(createActivity({})).rejects.toThrowError('Fields must be provided');
    });
  });

  describe('searchIssues', () => {
    it('should return issues with valid JQL and fields', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      const response = await searchIssues({ jql: 'project = YOUR_PROJECT_KEY', fields: ['id', 'summary'] });
      expect(response.issues.length).toBeGreaterThan(0);
    });

    it('should throw an error if JQL is missing', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'your-username',
        password: 'your-password'
      });

      await expect(searchIssues({ fields: ['id', 'summary'] })).rejects.toThrowError('JQL must be provided');
    });
  });
});

describe('Activity', () => {
  it('should create an Activity object with valid properties', () => {
    const activity = new Activity(123, 'New TypeScript Activity');
    expect(activity.id).toBe(123);
    expect(activity.title).toBe('New TypeScript Activity');
  });

  it('should throw an error if id is missing', () => {
    const activity = new Activity(undefined, 'New TypeScript Activity');
    expect(() => new Activity(undefined, 'New TypeScript Activity')).toThrowError('id must be provided');
  });
});
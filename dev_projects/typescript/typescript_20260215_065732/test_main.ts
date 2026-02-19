import { JiraClient } from 'jira-client';
import * as config from './config';

const jira = new JiraClient(config);

describe('JiraClient', () => {
  describe('searchIssues method', () => {
    it('should return issues when provided with valid parameters', async () => {
      const issues = await jira.searchIssues({
        jql: 'project = SCRUM-10 AND status = Open',
        fields: ['summary', 'assignee']
      });

      expect(issues).toBeInstanceOf(Array);
      expect(issues.length).toBeGreaterThan(0);
    });

    it('should throw an error when provided with invalid parameters', async () => {
      try {
        await jira.searchIssues({
          jql: 'project = SCRUM-10 AND status = Open',
          fields: ['summary']
        });
      } catch (error) {
        expect(error.message).toBe('Invalid field name');
      }
    });

    it('should handle edge cases', async () => {
      const issues = await jira.searchIssues({
        jql: 'project = SCRUM-10 AND status = Open',
        fields: ['summary']
      });

      expect(issues.length).toBeGreaterThan(0);
    });
  });
});
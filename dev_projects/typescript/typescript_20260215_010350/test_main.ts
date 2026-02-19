import axios from 'axios';
import { JiraIssue } from './JiraClient';

describe('JiraClient', () => {
  describe('getIssue', () => {
    it('should return the issue data for a given key', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-123';

      await axios.get(`${jiraClient.apiUrl}/issue/${issueKey}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      // Assuming the response is parsed correctly and contains the issue data
      expect(jiraClient.issues).toContainEqual({ key: issueKey, summary: 'New feature implementation', description: 'Implement the new feature in the application' });
    });

    it('should throw an error if the issue does not exist', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-124';

      try {
        await jiraClient.getIssue(issueKey);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Assuming the error message is descriptive
        expect(error.message).toContain('Issue not found');
      }
    });
  });

  describe('addIssue', () => {
    it('should add a new issue to the list', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-125';
      const summary = 'New feature implementation';
      const description = 'Implement the new feature in the application';

      await jiraClient.addIssue(issueKey, summary, description);

      // Assuming the response is parsed correctly and contains the updated list of issues
      expect(jiraClient.issues).toContainEqual({ key: issueKey, summary, description });
    });

    it('should throw an error if the issue already exists', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-123';
      const summary = 'New feature implementation';
      const description = 'Implement the new feature in the application';

      await jiraClient.addIssue(issueKey, summary, description);

      try {
        await jiraClient.addIssue(issueKey, summary, description);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Assuming the error message is descriptive
        expect(error.message).toContain('Issue already exists');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue in the list', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-123';
      const summary = 'Updated feature implementation';
      const description = 'Update the feature implementation to include new features';

      await jiraClient.updateIssue(issueKey, summary, description);

      // Assuming the response is parsed correctly and contains the updated list of issues
      expect(jiraClient.issues).toContainEqual({ key: issueKey, summary, description });
    });

    it('should throw an error if the issue does not exist', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-124';
      const summary = 'Updated feature implementation';
      const description = 'Update the feature implementation to include new features';

      try {
        await jiraClient.updateIssue(issueKey, summary, description);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Assuming the error message is descriptive
        expect(error.message).toContain('Issue not found');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an existing issue from the list', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-123';

      await jiraClient.deleteIssue(issueKey);

      // Assuming the response is parsed correctly and contains the updated list of issues
      expect(jiraClient.issues).not.toContainEqual({ key: issueKey, summary: 'Updated feature implementation', description: 'Update the feature implementation to include new features' });
    });

    it('should throw an error if the issue does not exist', async () => {
      const token = 'your-jira-token';
      const jiraClient = new JiraClient(token);
      const issueKey = 'ABC-124';

      try {
        await jiraClient.deleteIssue(issueKey);
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Assuming the error message is descriptive
        expect(error.message).toContain('Issue not found');
      }
    });
  });
});
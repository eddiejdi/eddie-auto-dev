import axios from 'axios';
import { JiraClient } from '@jira/client';

describe('JiraClientTypeScript', () => {
  let jiraClient: JiraClient;

  beforeEach(() => {
    const token = 'YOUR_JIRA_TOKEN';
    const baseUrl = 'https://your-jira-instance.atlassian.net';
    jiraClient = new JiraClient(token, baseUrl);
  });

  describe('createIssue', () => {
    it('should create an issue with valid data', async () => {
      await jiraClient.createIssue('Novo Título', 'Nova descrição');
      // Add assertions to check if the issue was created successfully
    });

    it('should throw an error when creating an issue with invalid data', async () => {
      try {
        await jiraClient.createIssue('', '');
        fail('Expected an error to be thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Add assertions to check if the error message is correct
      }
    });
  });

  describe('listIssues', () => {
    it('should list issues with valid data', async () => {
      await jiraClient.listIssues();
      // Add assertions to check if the issues were listed successfully
    });

    it('should throw an error when listing issues with invalid data', async () => {
      try {
        await jiraClient.listIssues('');
        fail('Expected an error to be thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Add assertions to check if the error message is correct
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an issue with valid data', async () => {
      await jiraClient.updateIssue('ISSUE_ID', 'Novo título atualizado', 'Nova descrição atualizada');
      // Add assertions to check if the issue was updated successfully
    });

    it('should throw an error when updating an issue with invalid data', async () => {
      try {
        await jiraClient.updateIssue('', '', '');
        fail('Expected an error to be thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Add assertions to check if the error message is correct
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue with valid data', async () => {
      await jiraClient.deleteIssue('ISSUE_ID');
      // Add assertions to check if the issue was deleted successfully
    });

    it('should throw an error when deleting an issue with invalid data', async () => {
      try {
        await jiraClient.deleteIssue('');
        fail('Expected an error to be thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        // Add assertions to check if the error message is correct
      }
    });
  });
});
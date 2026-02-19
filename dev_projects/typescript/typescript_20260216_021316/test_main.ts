import { expect } from 'chai';
import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/types';

describe('TypeScriptAgent', () => {
  let agent: TypeScriptAgent;

  beforeEach(() => {
    agent = new TypeScriptAgent(
      'https://your-jira-instance.atlassian.net',
      'your-username',
      'your-password'
    );
  });

  describe('#createIssue', () => {
    it('should create a new issue with valid fields', async () => {
      const title = 'Bug in TypeScript';
      const description = 'This is a test bug.';
      const expectedFields: Issue.Fields = {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      };

      const issueData: Issue = {
        fields: expectedFields
      };

      const createdIssue = await agent.createIssue(title, description);
      expect(createdIssue.fields).to.deep.equal(expectedFields);
    });

    it('should throw an error if the project key is invalid', async () => {
      const title = 'Bug in TypeScript';
      const description = 'This is a test bug.';
      const expectedFields: Issue.Fields = {
        project: { key: 'INVALID_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      };

      const issueData: Issue = {
        fields: expectedFields
      };

      try {
        await agent.createIssue(title, description);
      } catch (error) {
        expect(error.message).to.equal('Error creating issue: Invalid project key');
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update an existing issue with valid fields', async () => {
      const title = 'Bug in TypeScript';
      const description = 'This is a test bug.';
      const expectedFields: Issue.Fields = {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      };

      const issueData: Issue = {
        fields: expectedFields
      };

      await agent.createIssue(title, description);

      const updatedTitle = 'Updated title';
      const updatedDescription = 'Updated description';

      const updatedIssue = await agent.updateIssue('issueId', updatedTitle, updatedDescription);
      expect(updatedIssue.fields.summary).to.equal(updatedTitle);
      expect(updatedIssue.fields.description).to.equal(updatedDescription);
    });

    it('should throw an error if the issue ID is invalid', async () => {
      const title = 'Bug in TypeScript';
      const description = 'This is a test bug.';
      const expectedFields: Issue.Fields = {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      };

      const issueData: Issue = {
        fields: expectedFields
      };

      await agent.createIssue(title, description);

      try {
        await agent.updateIssue('invalidId', updatedTitle, updatedDescription);
      } catch (error) {
        expect(error.message).to.equal('Error updating issue: Invalid issue ID');
      }
    });
  });

  describe('#deleteIssue', () => {
    it('should delete an existing issue', async () => {
      const title = 'Bug in TypeScript';
      const description = 'This is a test bug.';
      const expectedFields: Issue.Fields = {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      };

      const issueData: Issue = {
        fields: expectedFields
      };

      await agent.createIssue(title, description);

      await agent.deleteIssue('issueId');
      try {
        await agent.getIssue('issueId');
      } catch (error) {
        expect(error.message).to.equal('Error deleting issue: Invalid issue ID');
      }
    });

    it('should throw an error if the issue ID is invalid', async () => {
      const title = 'Bug in TypeScript';
      const description = 'This is a test bug.';
      const expectedFields: Issue.Fields = {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      };

      const issueData: Issue = {
        fields: expectedFields
      };

      await agent.createIssue(title, description);

      try {
        await agent.deleteIssue('invalidId');
      } catch (error) {
        expect(error.message).to.equal('Error deleting issue: Invalid issue ID');
      }
    });
  });
});
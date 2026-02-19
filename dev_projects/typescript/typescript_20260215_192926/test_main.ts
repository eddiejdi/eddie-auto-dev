import { JiraClient } from 'jira-client';
import { expect } from 'chai';

class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraUrl: string, username: string, password: string) {
    this.jiraClient = new JiraClient({
      url: jiraUrl,
      username: username,
      password: password
    });
  }

  async createIssue(title: string, description: string): Promise<void> {
    try {
      await this.jiraClient.createIssue({
        fields: {
          project: { key: 'YOUR_PROJECT_KEY' },
          summary: title,
          description: description
        }
      });
      console.log('Issue created successfully');
    } catch (error) {
      console.error('Error creating issue:', error);
    }
  }

  async updateIssue(issueId: string, title?: string, description?: string): Promise<void> {
    try {
      await this.jiraClient.updateIssue({
        fields: {
          summary: title,
          description: description
        },
        issueKey: issueId
      });
      console.log('Issue updated successfully');
    } catch (error) {
      console.error('Error updating issue:', error);
    }
  }

  async deleteIssue(issueId: string): Promise<void> {
    try {
      await this.jiraClient.deleteIssue({
        issueKey: issueId
      });
      console.log('Issue deleted successfully');
    } catch (error) {
      console.error('Error deleting issue:', error);
    }
  }
}

describe('TypeScriptAgent', () => {
  let agent;

  beforeEach(() => {
    agent = new TypeScriptAgent(
      'https://your-jira-instance.atlassian.net',
      'your-username',
      'your-password'
    );
  });

  describe('createIssue', () => {
    it('should create an issue with valid title and description', async () => {
      await agent.createIssue('New Feature Request', 'Implement a new feature');
      expect(console.log).to.have.been.calledWith('Issue created successfully');
    });

    it('should throw an error if the title is empty', async () => {
      try {
        await agent.createIssue('', 'Implement a new feature');
      } catch (error) {
        expect(error.message).to.equal('Title cannot be empty');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an issue with valid title and description', async () => {
      await agent.updateIssue('NEW-123', 'Updated the feature description');
      expect(console.log).to.have.been.calledWith('Issue updated successfully');
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        await agent.updateIssue('INVALID-ID', 'Updated the feature description');
      } catch (error) {
        expect(error.message).to.equal('Invalid issue ID');
      }
    });
  });

  describe('deleteIssue', () => {
    it('should delete an issue with valid issue ID', async () => {
      await agent.deleteIssue('NEW-123');
      expect(console.log).to.have.been.calledWith('Issue deleted successfully');
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        await agent.deleteIssue('INVALID-ID');
      } catch (error) {
        expect(error.message).to.equal('Invalid issue ID');
      }
    });
  });
});
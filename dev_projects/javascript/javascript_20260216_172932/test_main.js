const { expect } = require('chai');
const jsAgent = require('js-agent');

describe('JavaScript Agent', () => {
  describe('createIssue', () => {
    it('should create a new issue with valid fields', async () => {
      const response = await jsAgent.createIssue({
        fields: {
          project: { key: 'YOUR-PROJECT' },
          summary: 'Bug in login page',
          description: 'The login page is not working properly.',
          issuetype: { name: 'Bug' }
        }
      });

      expect(response).to.have.property('id');
    });

    it('should throw an error if the project key is invalid', async () => {
      try {
        await jsAgent.createIssue({
          fields: {
            project: { key: 'INVALID-PROJECT' },
            summary: 'Bug in login page',
            description: 'The login page is not working properly.',
            issuetype: { name: 'Bug' }
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid project key');
      }
    });

    it('should throw an error if the summary field is empty', async () => {
      try {
        await jsAgent.createIssue({
          fields: {
            project: { key: 'YOUR-PROJECT' },
            summary: '',
            description: 'The login page is not working properly.',
            issuetype: { name: 'Bug' }
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Summary field cannot be empty');
      }
    });

    it('should throw an error if the description field is empty', async () => {
      try {
        await jsAgent.createIssue({
          fields: {
            project: { key: 'YOUR-PROJECT' },
            summary: 'Bug in login page',
            description: '',
            issuetype: { name: 'Bug' }
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Description field cannot be empty');
      }
    });

    it('should throw an error if the issuetype field is invalid', async () => {
      try {
        await jsAgent.createIssue({
          fields: {
            project: { key: 'YOUR-PROJECT' },
            summary: 'Bug in login page',
            description: 'The login page is not working properly.',
            issuetype: { name: 'INVALID-TYPE' }
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid issue type');
      }
    });
  });

  describe('updateIssue', () => {
    it('should update an existing issue with valid fields', async () => {
      const response = await jsAgent.updateIssue({
        issueKey: '12345',
        fields: {
          summary: 'Fixed the login page issue.',
          description: 'The login page now works correctly.'
        }
      });

      expect(response).to.have.property('id');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await jsAgent.updateIssue({
          issueKey: 'INVALID-KEY',
          fields: {
            summary: 'Fixed the login page issue.',
            description: 'The login page now works correctly.'
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid issue key');
      }
    });

    it('should throw an error if the summary field is empty', async () => {
      try {
        await jsAgent.updateIssue({
          issueKey: '12345',
          fields: {
            summary: '',
            description: 'The login page now works correctly.'
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Summary field cannot be empty');
      }
    });

    it('should throw an error if the description field is empty', async () => {
      try {
        await jsAgent.updateIssue({
          issueKey: '12345',
          fields: {
            summary: 'Fixed the login page issue.',
            description: ''
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Description field cannot be empty');
      }
    });

    it('should throw an error if the issuetype field is invalid', async () => {
      try {
        await jsAgent.updateIssue({
          issueKey: '12345',
          fields: {
            summary: 'Fixed the login page issue.',
            description: 'The login page now works correctly.',
            issuetype: { name: 'INVALID-TYPE' }
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid issue type');
      }
    });
  });

  describe('closeIssue', () => {
    it('should close an existing issue with valid fields', async () => {
      const response = await jsAgent.updateIssue({
        issueKey: '12345',
        fields: {
          status: { name: 'Closed' }
        }
      });

      expect(response).to.have.property('id');
    });

    it('should throw an error if the issue key is invalid', async () => {
      try {
        await jsAgent.updateIssue({
          issueKey: 'INVALID-KEY',
          fields: {
            status: { name: 'Closed' }
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid issue key');
      }
    });

    it('should throw an error if the status field is invalid', async () => {
      try {
        await jsAgent.updateIssue({
          issueKey: '12345',
          fields: {
            status: { name: 'INVALID-STATUS' }
          }
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid status');
      }
    });
  });

  describe('listIssues', () => {
    it('should list all issues for the current user with valid JQL query', async () => {
      const response = await jsAgent.searchIssues({
        jql: 'assignee = currentUser()'
      });

      expect(response.issues).to.have.lengthOf.above(0);
    });

    it('should throw an error if the JQL query is invalid', async () => {
      try {
        await jsAgent.searchIssues({
          jql: 'INVALID-JQL-QUERY'
        });
      } catch (error) {
        expect(error).to.have.property('message').that.includes('Invalid JQL query');
      }
    });
  });
});
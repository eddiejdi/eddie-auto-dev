import axios from 'axios';
import { expect } from 'chai';

describe('JiraClient', () => {
  let jiraClient: JiraClient;

  beforeEach(() => {
    jiraClient = new JiraClient(
      'https://your-jira-instance.atlassian.net/rest/api/2',
      'your-access-token'
    );
  });

  describe('#fetchIssues', () => {
    it('should return issues for a valid query', async () => {
      const response = await jiraClient.fetchIssues('project=YOUR_PROJECT');
      expect(response).to.be.an('array');
      expect(response.length).greaterThan(0);
    });

    it('should throw an error if the query is invalid', async () => {
      try {
        await jiraClient.fetchIssues('invalid-query');
      } catch (error) {
        expect(error.message).to.equal('Erro ao buscar tarefas: Invalid query');
      }
    });
  });

  describe('#createIssue', () => {
    it('should create a new issue with valid fields', async () => {
      const newIssue = {
        fields: {
          project: { key: 'YOUR_PROJECT' },
          summary: 'Novo teste',
          description: 'Este é um novo teste para a integração com Jira.',
          priority: { name: 'High' },
          status: { name: 'To Do' }
        }
      };
      const createdIssue = await jiraClient.createIssue(newIssue);
      expect(createdIssue).to.have.property('id');
    });

    it('should throw an error if the issue fields are invalid', async () => {
      try {
        const newIssue = {
          fields: {
            project: { key: 'YOUR_PROJECT' },
            summary: '',
            description: 'Este é um novo teste para a integração com Jira.',
            priority: { name: 'High' },
            status: { name: 'To Do' }
          }
        };
        await jiraClient.createIssue(newIssue);
      } catch (error) {
        expect(error.message).to.equal('Erro ao criar tarefa: Invalid issue fields');
      }
    });
  });

  describe('#updateIssue', () => {
    it('should update an existing issue with valid fields', async () => {
      const issueId = 'YOUR_ISSUE_ID';
      const updatedIssue = {
        fields: {
          summary: 'Atualizado teste'
        }
      };
      await jiraClient.updateIssue(issueId, updatedIssue);
      expect(updatedIssue).to.have.property('id');
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        const issueId = '';
        const updatedIssue = {
          fields: {
            summary: 'Atualizado teste'
          }
        };
        await jiraClient.updateIssue(issueId, updatedIssue);
      } catch (error) {
        expect(error.message).to.equal('Erro ao atualizar tarefa: Invalid issue ID');
      }
    });
  });

  describe('#deleteIssue', () => {
    it('should delete an existing issue with valid ID', async () => {
      const issueId = 'YOUR_ISSUE_ID';
      await jiraClient.deleteIssue(issueId);
      expect(jiraClient).to.have.property('issues').that.is.an('array');
    });

    it('should throw an error if the issue ID is invalid', async () => {
      try {
        const issueId = '';
        await jiraClient.deleteIssue(issueId);
      } catch (error) {
        expect(error.message).to.equal('Erro ao deletar tarefa: Invalid issue ID');
      }
    });
  });

  describe('#logError', () => {
    it('should log an error with valid fields', async () => {
      try {
        throw new Error('Teste de erro');
      } catch (error) {
        await jiraClient.logError(error);
        expect(jiraClient).to.have.property('issues').that.is.an('array');
      }
    });
  });
});
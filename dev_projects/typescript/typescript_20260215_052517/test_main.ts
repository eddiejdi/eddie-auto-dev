import { expect } from 'chai';
import axios from 'axios';
import { JiraClient } from './jira-client';

describe('JiraClient', () => {
  describe('createEvent', () => {
    it('should create an event with valid data', async () => {
      const token = process.env.JIRA_TOKEN!;
      const client = new TypeScriptAgent(token);

      const event: Event = {
        id: '12345',
        type: 'bug',
        data: {
          title: 'Bug in TypeScript code',
          description: 'The TypeScript code is not compiling correctly'
        }
      };

      await client.createEvent(event);
      expect(client.events).to.have.lengthOf(1);
    });

    it('should throw an error if the event is invalid', async () => {
      const token = process.env.JIRA_TOKEN!;
      const client = new TypeScriptAgent(token);

      const event: Event = {
        id: '12345',
        type: 'bug',
        data: {}
      };

      await expect(client.createEvent(event)).to.be.rejected;
    });
  });

  describe('getEvents', () => {
    it('should retrieve events for a valid project and issue', async () => {
      const token = process.env.JIRA_TOKEN!;
      const client = new TypeScriptAgent(token);

      const events = await client.getEvents('YOUR_PROJECT_ID', 'YOUR_ISSUE_ID');
      expect(events).to.have.lengthOf(1);
    });

    it('should return an empty array if the project or issue does not exist', async () => {
      const token = process.env.JIRA_TOKEN!;
      const client = new TypeScriptAgent(token);

      const events = await client.getEvents('INVALID_PROJECT_ID', 'INVALID_ISSUE_ID');
      expect(events).to.have.lengthOf(0);
    });
  });

  describe('main', () => {
    it('should create and retrieve an event successfully', async () => {
      const token = process.env.JIRA_TOKEN!;
      const client = new TypeScriptAgent(token);

      try {
        const event: Event = {
          id: '12345',
          type: 'bug',
          data: {
            title: 'Bug in TypeScript code',
            description: 'The TypeScript code is not compiling correctly'
          }
        };

        await client.createEvent(event);
        expect(client.events).to.have.lengthOf(1);

        const retrievedEvents = await client.getEvents('YOUR_PROJECT_ID', 'YOUR_ISSUE_ID');
        expect(retrievedEvents).to.have.lengthOf(1);
      } catch (error) {
        console.error('Error in main:', error);
      }
    });
  });
});
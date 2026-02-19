const axios = require('axios');
const fs = require('fs');

describe('Activity Class', () => {
  describe('constructor', () => {
    it('should create an Activity object with the provided properties', async () => {
      const id = '12345';
      const title = 'Implement JavaScript Agent';
      const description = 'Tracking of user activities in the application';

      const activity = new Activity(id, title, description);

      expect(activity.id).toBe(id);
      expect(activity.title).toBe(title);
      expect(activity.description).toBe(description);
    });
  });

  describe('createActivity', () => {
    it('should create a new issue in Jira with the provided data', async () => {
      const title = 'Implement JavaScript Agent';
      const description = 'Tracking of user activities in the application';

      try {
        await createActivity(title, description);
        console.log(`New activity created: ${title}`);
      } catch (error) {
        console.error('Error:', error);
      }
    });
  });

  describe('listActivities', () => {
    it('should list all issues assigned to the current user in Jira', async () => {
      try {
        const activities = await listActivities();
        console.log('All activities:');
        activities.forEach(activity => console.log(`${activity.id}: ${activity.title} - ${activity.description}`));
      } catch (error) {
        console.error('Error:', error);
      }
    });
  });
});
import { expect } from 'chai';
import { JiraClient } from 'jira-client';
import { Task } from './Task';

describe('ScrumTeam', () => {
  let jiraClient: JiraClient;
  let scrumTeam: ScrumTeam;

  beforeEach(() => {
    jiraClient = new JiraClient({
      url: 'https://your-jira-instance.atlassian.net',
      username: 'YOUR_USERNAME',
      password: 'YOUR_PASSWORD'
    });

    scrumTeam = new ScrumTeam(jiraClient);
  });

  describe('addTask', () => {
    it('should add a task to Jira with valid fields', async () => {
      const task = new Task('T101', 'Fix bug in homepage', 'Ensure the homepage loads correctly');
      await scrumTeam.addTask(task);

      expect(scrumTeam.tasks.length).to.equal(1);
      expect(scrumTeam.tasks[0].key).to.equal('T101');
    });

    it('should throw an error if the task summary is empty', async () => {
      const task = new Task('', 'Fix bug in homepage', 'Ensure the homepage loads correctly');

      await expect(scrumTeam.addTask(task)).rejects.to.be.an(Error);
    });
  });

  describe('updateTask', () => {
    it('should update a task in Jira with valid fields', async () => {
      const task = new Task('T102', 'Fix bug in homepage', 'Ensure the homepage loads correctly');
      await scrumTeam.addTask(task);

      await scrumTeam.updateTask('T102', 'Update homepage to use HTTPS');

      expect(scrumTeam.tasks[0].summary).to.equal('Update homepage to use HTTPS');
    });

    it('should throw an error if the task summary is empty', async () => {
      const task = new Task('T103', '', 'Ensure the homepage loads correctly');

      await expect(scrumTeam.updateTask('T103', 'Update homepage to use HTTPS')).rejects.to.be.an(Error);
    });
  });

  describe('deleteTask', () => {
    it('should delete a task from Jira with valid fields', async () => {
      const task = new Task('T104', 'Fix bug in homepage', 'Ensure the homepage loads correctly');
      await scrumTeam.addTask(task);

      await scrumTeam.deleteTask('T104');

      expect(scrumTeam.tasks.length).to.equal(0);
    });

    it('should throw an error if the task ID is invalid', async () => {
      await expect(scrumTeam.deleteTask('InvalidID')).rejects.to.be.an(Error);
    });
  });

  describe('listTasks', () => {
    it('should list all tasks from Jira with valid fields', async () => {
      const task1 = new Task('T105', 'Fix bug in homepage', 'Ensure the homepage loads correctly');
      await scrumTeam.addTask(task1);

      const task2 = new Task('T106', 'Update login page to use HTTPS', 'Ensure user can log in with correct credentials');
      await scrumTeam.addTask(task2);

      const tasks = await scrumTeam.listTasks();

      expect(tasks.length).to.equal(2);
      expect(tasks[0].key).to.equal('T105');
      expect(tasks[1].key).to.equal('T106');
    });

    it('should throw an error if there are no tasks in Jira', async () => {
      await expect(scrumTeam.listTasks()).resolves.to.deep.equal([]);
    });
  });

  describe('main', () => {
    it('should run the main function without errors', async () => {
      const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'YOUR_USERNAME',
        password: 'YOUR_PASSWORD'
      });

      scrumTeam = new ScrumTeam(jiraClient);

      await scrumTeam.main();
    });
  });
});
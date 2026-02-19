import axios from 'axios';
import { Task } from './task';

// Teste para criar uma nova tarefa
test('createTask should return a new task', async () => {
  const task = {
    fields: {
      project: { key: 'YOUR-PROJECT' },
      summary: 'Implement TypeScript integration with Jira',
      description: 'This task is to integrate TypeScript with Jira using the REST API.',
      issuetype: { name: 'Bug' }
    }
  };

  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', task);
    expect(response.status).toBe(201);
    expect(response.data).toEqual(task);
  } catch (error) {
    console.error('Error creating task:', error);
  }
});

// Teste para atualizar uma tarefa
test('updateTask should return the updated task', async () => {
  const task = {
    fields: {
      project: { key: 'YOUR-PROJECT' },
      summary: 'Implement TypeScript integration with Jira',
      description: 'This task is to integrate TypeScript with Jira using the REST API.',
      issuetype: { name: 'Bug' }
    }
  };

  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', task);
    const taskId = response.data.id;

    const updatedTask = {
      fields: {
        status: { name: 'In Progress' }
      },
      id: taskId
    };

    const updatedResponse = await axios.put(`https://your-jira-instance.atlassian.net/rest/api/2/issue/${taskId}`, updatedTask);
    expect(updatedResponse.status).toBe(200);
    expect(updatedResponse.data).toEqual(updatedTask);
  } catch (error) {
    console.error('Error updating task:', error);
  }
});

// Teste para buscar uma tarefa pelo ID
test('getTask should return the task details', async () => {
  const task = {
    fields: {
      project: { key: 'YOUR-PROJECT' },
      summary: 'Implement TypeScript integration with Jira',
      description: 'This task is to integrate TypeScript with Jira using the REST API.',
      issuetype: { name: 'Bug' }
    }
  };

  try {
    const response = await axios.post('https://your-jira-instance.atlassian.net/rest/api/2/issue', task);
    const taskId = response.data.id;

    const updatedTask = {
      fields: {
        status: { name: 'In Progress' }
      },
      id: taskId
    };

    const updatedResponse = await axios.put(`https://your-jira-instance.atlassian.net/rest/api/2/issue/${taskId}`, updatedTask);
    expect(updatedResponse.status).toBe(200);
    expect(updatedResponse.data).toEqual(updatedTask);
  } catch (error) {
    console.error('Error updating task:', error);
  }
});

// Teste para listar todas as tarefas do usuário
test('listTasks should return an array of tasks', async () => {
  try {
    const response = await axios.get(`https://your-jira-instance.atlassian.net/rest/api/2/myself/issue`);
    expect(response.status).toBe(200);
    expect(Array.isArray(response.data)).toBe(true);
  } catch (error) {
    console.error('Error listing tasks:', error);
  }
});
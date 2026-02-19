import { JiraClient } from 'jira-client';
import { Issue } from 'jira-client/lib/models/issue';

// Define a classe para representar um problema (bug)
class Bug {
  id: string;
  title: string;
  description: string;

  constructor(id: string, title: string, description: string) {
    this.id = id;
    this.title = title;
    this.description = description;
  }
}

// Define a classe para representar um usuário
class User {
  id: string;
  name: string;

  constructor(id: string, name: string) {
    this.id = id;
    this.name = name;
  }
}

// Define a classe para representar uma atividade (task)
class Task {
  id: string;
  title: string;
  description: string;
  status: 'open' | 'in progress' | 'closed';

  constructor(id: string, title: string, description: string, status: 'open' | 'in progress' | 'closed') {
    this.id = id;
    this.title = title;
    this.description = description;
    this.status = status;
  }
}

// Define a classe para representar uma equipe
class Team {
  members: User[];
  name: string;

  constructor(name: string) {
    this.members = [];
    this.name = name;
  }

  addMember(user: User): void {
    this.members.push(user);
  }
}

// Define a classe para representar um projeto
class Project {
  id: string;
  name: string;
  team: Team;

  constructor(id: string, name: string, team: Team) {
    this.id = id;
    this.name = name;
    this.team = team;
  }

  addTask(task: Task): void {
    task.status = 'open';
    this.team.tasks.push(task);
  }
}

// Define a classe para representar o sistema de tipos avançado
class TypeScriptAgent {
  private jiraClient: JiraClient;

  constructor(jiraClient: JiraClient) {
    this.jiraClient = jiraClient;
  }

  async fetchIssues(): Promise<Issue[]> {
    const issues = await this.jiraClient.search('type issue');
    return issues.map(issue => new Issue(issue));
  }

  async createBug(title: string, description: string): Promise<Bug> {
    const issue = await this.jiraClient.createIssue({
      fields: {
        project: { key: 'YOUR_PROJECT_KEY' },
        summary: title,
        description: description,
        issuetype: { name: 'Bug' }
      }
    });
    return new Bug(issue.id, title, description);
  }

  async updateTask(taskId: string, status: 'open' | 'in progress' | 'closed'): Promise<void> {
    await this.jiraClient.updateIssue({
      issueKey: taskId,
      fields: { status }
    });
  }

  async closeBug(bugId: string): Promise<void> {
    await this.updateTask(bugId, 'closed');
  }

  async main(): Promise<void> {
    const jiraClient = new JiraClient({
      options: {
        basicAuth: {
          username: 'YOUR_JIRA_USERNAME',
          password: 'YOUR_JIRA_PASSWORD'
        }
      }
    });

    try {
      const issues = await this.fetchIssues();
      console.log('Issues:', issues);

      const bug = await this.createBug('Test Bug', 'This is a test bug.');
      console.log('Created bug:', bug);

      await this.updateTask(bug.id, 'in progress');
      console.log('Updated task status to in progress.');

      await this.closeBug(bug.id);
      console.log('Closed bug:', bug);

    } catch (error) {
      console.error('Error:', error);
    }
  }
}

// Define a função main() ou ponto de entrada
async function main(): Promise<void> {
  const agent = new TypeScriptAgent(new JiraClient({
    options: {
      basicAuth: {
        username: 'YOUR_JIRA_USERNAME',
        password: 'YOUR_JIRA_PASSWORD'
      }
    }
  }));

  await agent.main();
}

// Execute a função main() ou ponto de entrada
if (require.main === module) {
  main().catch(error => console.error('Error:', error));
}
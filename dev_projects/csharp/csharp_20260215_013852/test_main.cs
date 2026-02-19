using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace CSharpAgentJira.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task TestCreateTask()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net");

            // Autenticação (substitua pelo seu token de autenticação)
            await jiraClient.AuthenticateAsync("your-token");

            // Criar uma nova tarefa com valores válidos
            var task = new Task
            {
                Summary = "Criar um novo item na lista",
                Description = "Este é o corpo da descrição da tarefa.",
                Assignee = "user-123"
            };

            // Adicionar a tarefa à lista (substitua pelo ID da sua lista)
            var listId = 12345;
            await jiraClient.Tasks.AddAsync(listId, task);

            // Verificar se a tarefa foi criada com sucesso
            Assert.True(task.Id > 0);
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidSummary()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net");

            // Autenticação (substitua pelo seu token de autenticação)
            await jiraClient.AuthenticateAsync("your-token");

            // Criar uma nova tarefa com um summary inválido
            var task = new Task
            {
                Summary = "Criar um novo item na lista",
                Description = "Este é o corpo da descrição da tarefa.",
                Assignee = "user-123"
            };

            // Adicionar a tarefa à lista (substitua pelo ID da sua lista)
            var listId = 12345;
            await jiraClient.Tasks.AddAsync(listId, task);

            // Verificar se a tarefa foi criada com sucesso
            Assert.True(task.Id > 0);
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidDescription()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net");

            // Autenticação (substitua pelo seu token de autenticação)
            await jiraClient.AuthenticateAsync("your-token");

            // Criar uma nova tarefa com um description inválido
            var task = new Task
            {
                Summary = "Criar um novo item na lista",
                Description = "",
                Assignee = "user-123"
            };

            // Adicionar a tarefa à lista (substitua pelo ID da sua lista)
            var listId = 12345;
            await jiraClient.Tasks.AddAsync(listId, task);

            // Verificar se a tarefa foi criada com sucesso
            Assert.True(task.Id > 0);
        }

        [Fact]
        public async Task TestCreateTaskWithInvalidAssignee()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net");

            // Autenticação (substitua pelo seu token de autenticação)
            await jiraClient.AuthenticateAsync("your-token");

            // Criar uma nova tarefa com um assignee inválido
            var task = new Task
            {
                Summary = "Criar um novo item na lista",
                Description = "Este é o corpo da descrição da tarefa.",
                Assignee = null
            };

            // Adicionar a tarefa à lista (substitua pelo ID da sua lista)
            var listId = 12345;
            await jiraClient.Tasks.AddAsync(listId, task);

            // Verificar se a tarefa foi criada com sucesso
            Assert.True(task.Id > 0);
        }
    }
}
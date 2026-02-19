using System;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateTaskAsync_WithValidInput_ReturnsTask()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Criar uma nova tarefa no Jira
            var task = await jiraClient.CreateTaskAsync(
                "New Task",
                "This is a new task created by CSharpAgentJiraIntegration.",
                "1000"
            );

            // Verifica se a tarefa foi criada com sucesso
            Assert.NotNull(task);
            Assert.NotEmpty(task.Id);
        }

        [Fact]
        public async Task CreateTaskAsync_WithInvalidInput_ReturnsNull()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Criar uma nova tarefa no Jira com valores inválidos
            var task = await jiraClient.CreateTaskAsync(
                string.Empty,
                null,
                0
            );

            // Verifica se a tarefa foi criada com sucesso
            Assert.Null(task);
        }
    }
}
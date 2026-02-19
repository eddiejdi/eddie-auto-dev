using System;
using System.Net.Http;
using System.Threading.Tasks;
using JiraNetCore.Client;
using JiraNetCore.Models;
using Xunit;

namespace YourNamespace.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueTest()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria uma nova tarefa com valores válidos
            var task = new Issue()
            {
                Summary = "Implementar SCRUM-14",
                Description = "Integração com Jira para tracking de atividades em csharp.",
                Priority = "High",
                Status = "To Do"
            };

            // Adiciona a nova tarefa ao projeto
            await jiraClient.Issue.CreateAsync("your-project-key", task);

            // Verifica se a tarefa foi criada com sucesso
            Assert.True(task.Id > 0);
        }

        [Fact]
        public async Task CreateIssueWithInvalidSummaryTest()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria uma nova tarefa com um summary inválido
            var task = new Issue()
            {
                Summary = "",
                Description = "Integração com Jira para tracking de atividades em csharp.",
                Priority = "High",
                Status = "To Do"
            };

            // Tenta adicionar a nova tarefa ao projeto
            await Assert.ThrowsAsync<HttpRequestException>(() => jiraClient.Issue.CreateAsync("your-project-key", task));
        }

        [Fact]
        public async Task CreateIssueWithNullSummaryTest()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria uma nova tarefa com um summary nulo
            var task = new Issue()
            {
                Summary = null,
                Description = "Integração com Jira para tracking de atividades em csharp.",
                Priority = "High",
                Status = "To Do"
            };

            // Tenta adicionar a nova tarefa ao projeto
            await Assert.ThrowsAsync<HttpRequestException>(() => jiraClient.Issue.CreateAsync("your-project-key", task));
        }
    }
}
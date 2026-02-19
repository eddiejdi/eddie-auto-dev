using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_Success()
        {
            // Inicializa a conexão com o Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria um novo issue no Jira
            var issue = new Issue()
            {
                Summary = "Teste do Agent",
                Description = "Este é um teste para o agent do JiraSharp.Client.",
                Priority = 3,
                Status = 1
            };

            // Inclui o issue no Jira
            await jiraClient.CreateIssueAsync(issue);

            // Verifica se o issue foi criado com sucesso
            Assert.True(issue.Id != null);
        }

        [Fact]
        public async Task CreateIssueAsync_Failure()
        {
            // Inicializa a conexão com o Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria um novo issue no Jira com valores inválidos
            var issue = new Issue()
            {
                Summary = null,
                Description = "",
                Priority = -1,
                Status = 0
            };

            // Tenta incluir o issue no Jira e verifica se ocorre uma exceção
            await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.CreateIssueAsync(issue));
        }

        [Fact]
        public async Task GetIssuesAsync_Success()
        {
            // Inicializa a conexão com o Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Lista todas as issues do Jira
            var issues = await jiraClient.GetIssuesAsync();

            // Verifica se a lista de issues não está vazia
            Assert.NotEmpty(issues);
        }

        [Fact]
        public async Task GetIssuesAsync_Failure()
        {
            // Inicializa a conexão com o Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Tenta listar todas as issues do Jira e verifica se ocorre uma exceção
            await Assert.ThrowsAsync<Exception>(() => jiraClient.GetIssuesAsync());
        }
    }
}
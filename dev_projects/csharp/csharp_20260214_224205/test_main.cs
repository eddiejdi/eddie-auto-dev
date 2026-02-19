using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_Success()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria um novo issue
            var issue = new Issue
            {
                Key = "TEST-1",
                Summary = "Teste de integração C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Priority = new Priority { Name = "High" },
                Status = new Status { Name = "To Do" }
            };

            // Adiciona a issue ao projeto
            var project = await jiraClient.GetProjectAsync("your-project-key");
            var issueResult = await jiraClient.CreateIssueAsync(project.Key, issue);

            // Verifica se o issue foi criado com sucesso
            Assert.NotNull(issueResult);
            Assert.NotEmpty(issueResult.Id);
        }

        [Fact]
        public async Task CreateIssueAsync_Error()
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Cria um novo issue com valores inválidos
            var invalidIssue = new Issue
            {
                Key = "",
                Summary = null,
                Description = string.Empty,
                Priority = new Priority { Name = "" },
                Status = new Status { Name = "" }
            };

            // Tenta criar o issue e verifica se ocorre um erro
            try
            {
                await jiraClient.CreateIssueAsync("your-project-key", invalidIssue);
            }
            catch (Exception ex)
            {
                // Verifica se a exceção é do tipo JiraSharpException
                Assert.IsType<JiraSharpException>(ex);

                // Verifica o código de erro
                var error = ex as JiraSharpException;
                Assert.Equal("Invalid issue data", error.Message);
            }
        }
    }
}
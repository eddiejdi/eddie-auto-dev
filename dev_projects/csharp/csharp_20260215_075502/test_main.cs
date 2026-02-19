using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace CSharpAgent.JiraIntegration.Tests
{
    [TestClass]
    public class JiraServiceTests
    {
        private readonly string _jiraUrl = "http://localhost:8080";
        private readonly string _username = "admin";
        private readonly string _password = "admin";

        [TestMethod]
        public async Task CreateIssueAsync_Success()
        {
            var issue = new Issue
            {
                ProjectKey = "SCRUM-14",
                Summary = "Teste de criação de.issue",
                Description = "Descrição do teste",
                PriorityId = 1,
                StatusId = 2
            };

            var service = new JiraService(_jiraUrl, _username, _password);
            await service.CreateIssueAsync(issue);

            // Adicione aqui as verificações para o caso de sucesso
        }

        [TestMethod]
        public async Task CreateIssueAsync_Error()
        {
            var issue = new Issue
            {
                ProjectKey = "SCRUM-14",
                Summary = "",
                Description = "",
                PriorityId = 0,
                StatusId = 3
            };

            var service = new JiraService(_jiraUrl, _username, _password);
            await Assert.ThrowsAsync<ArgumentException>(() => service.CreateIssueAsync(issue));
        }

        // Adicione outros testes de sucesso e erro para as outras funções e métodos públicos
    }
}
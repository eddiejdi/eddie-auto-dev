using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

namespace CSharpAgent.JiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Cria uma nova tarefa em Jira
            var task = new Task()
            {
                Summary = "Implementar o CSharp Agent",
                Description = "Integração com ASP.NET Core, Entity Framework Core, LINQ e async/await",
                Assignee = "YourUsername"
            };

            // Adiciona a tarefa à lista de tarefas
            await jiraClient.Tasks.AddAsync(task);

            Console.WriteLine("Tarefa adicionada com sucesso!");
        }
    }
}
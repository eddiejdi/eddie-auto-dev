using System;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            // Criar uma nova tarefa no Jira
            var task = await jiraClient.CreateTaskAsync(
                "New Task",
                "This is a new task created by CSharpAgentJiraIntegration.",
                "1000"
            );

            Console.WriteLine($"Task created with ID: {task.Id}");
        }
    }
}
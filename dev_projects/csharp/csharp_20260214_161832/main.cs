using System;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do Jira API
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        try
        {
            // Cria um novo issue no Jira
            var issue = await jiraClient.CreateIssueAsync(
                summary: "New Task",
                description: "This is a new task for the project.",
                priority: "High",
                assignee: "user1"
            );

            Console.WriteLine($"Issue created with ID: {issue.Id}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating issue: {ex.Message}");
        }
    }
}
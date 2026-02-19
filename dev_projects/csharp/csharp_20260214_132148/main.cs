using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        try
        {
            // Cria um novo issue no Jira
            var issue = await jiraClient.CreateIssueAsync(
                "New Feature",
                "This is a new feature request.",
                "bug"
            );

            Console.WriteLine($"Issue created: {issue.Key}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating issue: {ex.Message}");
        }
    }
}
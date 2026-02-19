import com.atlassian.jira.rest.client.JiraRestClient;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.api.RestClientException;
import com.atlassian.jira.rest.client.api.issue.IssueService;
import com.atlassian.jira.rest.client.api.issue.Issue;
import com.atlassian.jira.rest.client.api.project.ProjectService;
import com.atlassian.jira.rest.client.api.project.Project;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;

import java.io.IOException;
import java.util.List;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraRestClient client = new JiraRestClient.Builder(JIRA_URL, new BasicHttpAuthenticationHandler(USERNAME, PASSWORD)).build()) {

            ProjectService projectService = client.getProjectService();
            List<Project> projects = projectService.getProjects();

            for (Project project : projects) {
                System.out.println("Project: " + project.getName());

                IssueService issueService = client.getIssueService();
                List<Issue> issues = issueService.searchIssues("project=" + project.getKey(), null, null);

                for (Issue issue : issues) {
                    System.out.println("  Issue: " + issue.getKey() + ", Summary: " + issue.getSummary());
                }
            }

        } catch (IOException | RestClientException e) {
            e.printStackTrace();
        }
    }
}
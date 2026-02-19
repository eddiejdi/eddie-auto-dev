import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;

import javax.ws.rs.GET;
import javax.ws.rs.Path;
import javax.ws.rs.Produces;
import javax.ws.rs.core.MediaType;
import java.util.List;

@Path("/jira")
@Produces(MediaType.APPLICATION_JSON)
public class JiraService {

    private final Jira jira;
    private final IssueManager issueManager;
    private final ProjectManager projectManager;

    public JiraService(Jira jira, IssueManager issueManager, ProjectManager projectManager) {
        this.jira = jira;
        this.issueManager = issueManager;
        this.projectManager = projectManager;
    }

    @GET
    public List<Issue> getIssues() {
        return issueManager.getAllIssues();
    }

    @GET
    @Path("/projects")
    public List<Project> getProjects() {
        return projectManager.getAllProjects();
    }
}
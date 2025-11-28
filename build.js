const https = require('https');
const fs = require('fs');
const path = require('path');

const NOTION_API_KEY = 'ntn_M100822564661lnf1DZr5LBPIwNs90MGXtftl70RCU57XT';
const DATABASE_ID = '2b203c184d6e80f0b0e9eb0f84f94089';

// Helper functions
function getPageTitle(page) {
    if (page.properties.Name?.title) {
        return page.properties.Name.title.map(t => t.plain_text).join('');
    }
    const titleProp = Object.values(page.properties).find(prop => prop.type === 'title');
    if (titleProp?.title) {
        return titleProp.title.map(t => t.plain_text).join('');
    }
    return 'Untitled';
}

function getViewOnlyLink(page) {
    if (page.url) {
        return `${page.url}?pvs=4`;
    }
    const cleanId = page.id.replace(/-/g, '');
    return `https://www.notion.so/${cleanId}?pvs=4`;
}

async function build() {
    console.log('Starting build process...');

    // 1. Fetch data from Notion
    console.log('Fetching articles from Notion...');
    const requestData = JSON.stringify({
        filter: {
            property: 'State',
            select: {
                equals: 'Published'
            }
        },
        sorts: [
            {
                property: 'Date',
                direction: 'descending'
            }
        ]
    });

    const options = {
        hostname: 'api.notion.com',
        path: `/v1/databases/${DATABASE_ID}/query`,
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${NOTION_API_KEY}`,
            'Notion-Version': '2022-06-28',
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(requestData)
        }
    };

    const notionData = await new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(data));
                    } catch (e) {
                        reject(new Error('Failed to parse Notion response'));
                    }
                } else {
                    reject(new Error(`Notion API failed with status ${res.statusCode}: ${data}`));
                }
            });
        });
        req.on('error', reject);
        req.write(requestData);
        req.end();
    });

    // 2. Generate HTML for articles
    console.log(`Found ${notionData.results?.length || 0} articles.`);
    let articlesHtml = '';
    if (notionData.results && notionData.results.length > 0) {
        notionData.results.forEach(page => {
            const title = getPageTitle(page);
            // Use title exactly as it is from Notion (user wants lowercase)

            const url = getViewOnlyLink(page);

            articlesHtml += `
            <div class="article-item">
                <div class="article-bullet"></div>
                <a href="${url}" target="_blank" rel="noopener noreferrer" class="article-link"><span class="text-rgb-0-0-255">${title}</span></a>
            </div>`;
        });
    } else {
        articlesHtml = '<p style="color: #666; font-style: italic;">No published articles found.</p>';
    }

    // 3. Inject into index.html
    console.log('Injecting content into index.html...');
    const indexPath = path.join(__dirname, 'index.html');
    let htmlContent = fs.readFileSync(indexPath, 'utf8');

    // Use markers for safe replacement
    const startMarker = '<!-- ARTICLES_START -->';
    const endMarker = '<!-- ARTICLES_END -->';

    const startIndex = htmlContent.indexOf(startMarker);
    const endIndex = htmlContent.indexOf(endMarker);

    if (startIndex !== -1 && endIndex !== -1) {
        const preContent = htmlContent.substring(0, startIndex + startMarker.length);
        const postContent = htmlContent.substring(endIndex);

        const newContent = `
        <div class="group-5-2" id="article-list">${articlesHtml}</div>`;

        const finalHtml = preContent + newContent + postContent;
        fs.writeFileSync(indexPath, finalHtml);
        console.log('Build complete! index.html updated.');
    } else {
        console.error('Error: Could not find markers in index.html');
        process.exit(1);
    }
}

build().catch(err => {
    console.error('Build failed:', err);
    process.exit(1);
});

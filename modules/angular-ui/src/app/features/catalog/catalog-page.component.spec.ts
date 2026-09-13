import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { CatalogApiService } from '../../core/services/catalog-api.service';
import { CatalogPageComponent } from './catalog-page.component';

describe('CatalogPageComponent', () => {
  it('loads facets and selects a detail after a catalog search', async () => {
    const resource = { resource_id: 'book-1', title: 'Architecture', authors: ['Ada'], tags: ['java'] };
    await TestBed.configureTestingModule({ imports: [CatalogPageComponent], providers: [{ provide: CatalogApiService, useValue: { facets: () => of({ facets: { authors: ['Ada'], tags: ['java'] } }), search: () => of({ total: 1, count: 1, limit: 20, offset: 0, resources: [resource] }), detail: () => of({ resource }) } }] }).compileComponents();
    const fixture = TestBed.createComponent(CatalogPageComponent);
    fixture.detectChanges();
    fixture.componentInstance.search(true);
    expect(fixture.componentInstance.facets().authors).toEqual(['Ada']);
    expect(fixture.componentInstance.selected()?.title).toBe('Architecture');
  });
});
